import configparser
import os
import sqlite3
import sys
from datetime import datetime, timedelta

import pytest

import runtime
from engine import Engine

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "plugins"))
from SqliteTarget import SqliteTarget  # noqa: E402

EP = "412"

# SqliteTarget (unchanged legacy plugin) inserts datetimes via sqlite3's
# default adapter, deprecated since Python 3.12.
pytestmark = pytest.mark.filterwarnings(
    "ignore:The default datetime adapter is deprecated:DeprecationWarning")


class LiveRecorder:
    enableArchive = False
    priority = 10
    tracks = []
    closed = 0

    def __init__(self, config, episode, episodeDate):
        pass

    def logTrack(self, track, startTime):
        LiveRecorder.tracks.append(track.title)

    def close(self):
        LiveRecorder.closed += 1


class FileRecorder:
    enableArchive = True
    priority = 0
    constructed = 0

    def __init__(self, config, episode, episodeDate):
        FileRecorder.constructed += 1

    def logTrack(self, track, startTime):
        pass

    def close(self):
        pass


class BadCloseLive(LiveRecorder):
    def close(self):
        raise RuntimeError("close boom")


class BrokenFile(FileRecorder):
    def logTrack(self, track, startTime):
        raise RuntimeError("file boom")


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACKUPDATE_RUNTIME_DIR", str(tmp_path / "rt"))
    LiveRecorder.tracks = []
    LiveRecorder.closed = 0
    FileRecorder.constructed = 0


@pytest.fixture
def config(tmp_path):
    c = configparser.ConfigParser()
    c.read_dict({
        "trackupdate": {"introAlbum": "", "ignoreAlbum": "", "useStopValues": "False",
                        "stopArtwork": "stop.jpg", "coverImageBaseURL": "http://c"},
        "SqliteTarget": {"enabled": "True", "dbPath": str(tmp_path / "t.db")},
    })
    return c


def rep(title):
    return {"trackName": title, "trackArtist": "Art " + title, "trackAlbum": "Alb",
            "trackLength": "3:00", "trackId": "id-" + title}


def clock():
    t = [datetime(2026, 10, 21, 20, 0, 0, 1)]

    def now():
        t[0] += timedelta(seconds=1)
        return t[0]
    return now


def make(config, reports, classes=(SqliteTarget, LiveRecorder, FileRecorder)):
    reports = list(reports)
    eng = Engine(config=config, episode=EP, plugin_classes=list(classes),
                 poller=lambda: reports.pop(0), artwork=lambda t, a: None,
                 now=clock())
    eng.start()
    return eng


def rows(config):
    conn = sqlite3.connect(config.get("SqliteTarget", "dbPath"))
    try:
        return conn.execute(
            "SELECT title FROM trackupdate ORDER BY rowid").fetchall()
    finally:
        conn.close()


def test_file_plugins_not_constructed_until_end_show(config):
    eng = make(config, [rep("A"), rep("B"), rep("C")])
    for _ in range(3):
        eng.tick()
    assert FileRecorder.constructed == 0
    eng.end_show()
    assert FileRecorder.constructed == 1


def test_tick_dispatches_to_live_plugins_and_db(config):
    eng = make(config, [rep("A"), rep("A"), rep("B")])
    for _ in range(3):
        eng.tick()
    assert LiveRecorder.tracks == ["A", "B"]
    assert rows(config) == [("A",), ("B",)]
    snap = eng.snapshot()
    assert snap["nowPlaying"]["title"] == "B"
    assert snap["nowPlaying"]["source"] == "swinsian"
    assert snap["currentRowid"] == snap["tracks"][-1]["rowid"]
    assert snap["tracks"][-1]["artworkUrl"] == "http://c/stop.jpg"


def test_edit_current_row_resends_without_new_row(config):
    eng = make(config, [rep("A")])
    eng.tick()
    rowid = eng.snapshot()["currentRowid"]
    eng.handle({"cmd": "edit_row", "rowid": rowid, "title": "Fixed",
                "artist": "Art A", "album": "Alb"})
    assert rows(config) == [("Fixed",)]
    assert LiveRecorder.tracks == ["A", "Fixed"]
    assert eng.snapshot()["nowPlaying"]["title"] == "Fixed"


def test_sqlite_cannot_be_toggled_off(config):
    eng = make(config, [rep("A"), rep("B")])
    eng.tick()
    eng.handle({"cmd": "toggle_plugin", "name": "SqliteTarget"})
    snap = eng.snapshot()
    assert snap["lastError"]
    sq = [p for p in snap["plugins"] if p["name"] == "SqliteTarget"][0]
    assert sq == {"name": "SqliteTarget", "kind": "live", "enabled": True,
                  "locked": True}
    eng.tick()
    assert rows(config) == [("A",), ("B",)]


def test_reenabling_live_plugin_pushes_current(config):
    eng = make(config, [rep("A"), rep("B")])
    eng.tick()
    eng.handle({"cmd": "toggle_plugin", "name": "LiveRecorder"})
    eng.tick()
    assert LiveRecorder.tracks == ["A"]
    eng.handle({"cmd": "toggle_plugin", "name": "LiveRecorder"})
    assert LiveRecorder.tracks == ["A", "B"]


def test_restart_mid_override_while_paused(config):
    a = make(config, [rep("A"), {}])
    a.tick()
    a.handle({"cmd": "set_override", "title": "Vinyl", "artist": "V",
              "album": "LP", "length": "4:00"})
    a.tick()
    assert rows(config) == [("A",), ("Vinyl",)]
    assert runtime.override_path().exists()

    b = make(config, [{}, rep("A")])
    assert b.snapshot()["overrideActive"] is True
    b.tick()
    assert rows(config) == [("A",), ("Vinyl",)]
    b.tick()
    assert rows(config) == [("A",), ("Vinyl",), ("A",)]
    assert not runtime.override_path().exists()
    assert b.snapshot()["overrideActive"] is False


def test_end_show_survives_failing_plugin(config):
    eng = make(config, [rep("A")],
               classes=(SqliteTarget, BadCloseLive, BrokenFile, FileRecorder))
    eng.tick()
    runtime.write_info(EP, os.getpid())
    seen = []
    eng.subscribe(seen.append)
    results = eng.end_show()
    by_name = {r["plugin"]: r for r in results}
    assert by_name["BrokenFile"]["ok"] is False
    assert by_name["BadCloseLive"]["ok"] is False
    assert by_name["FileRecorder"]["ok"] is True
    snap = eng.snapshot()
    assert snap["phase"] == "ended"
    assert snap["results"] == results
    assert [s["phase"] for s in seen] == ["ending", "ended"]
    assert not runtime.info_path().exists()


def test_bad_command_sets_last_error(config):
    eng = make(config, [rep("A")])
    eng.tick()
    seen = []
    eng.subscribe(seen.append)
    for cmd in ({"cmd": "nope"}, {"cmd": "edit_row", "rowid": 9999, "title": "x",
                                  "artist": "y", "album": "z"},
                {"cmd": "toggle_plugin", "name": "Missing"},
                {"cmd": "set_override", "title": "x"}, "garbage"):
        eng.handle(cmd)
        assert seen[-1]["lastError"]
    assert len(seen) == 5
    assert eng.snapshot()["phase"] == "live"


def test_poll_failure_sets_and_clears_error(config):
    eng = make(config, [None, rep("A")])
    eng.tick()
    assert eng.snapshot()["lastError"] == "Swinsian poll failed (see engine.log)"
    eng.tick()
    assert eng.snapshot()["lastError"] is None


def test_raising_listener_is_dropped(config):
    eng = make(config, [rep("A"), rep("B")])
    good = []

    def bad(snap):
        raise RuntimeError("listener boom")
    eng.subscribe(bad)
    eng.subscribe(good.append)
    eng.tick()
    eng.tick()
    assert len(good) == 2
    assert rows(config) == [("A",), ("B",)]


def test_run_processes_commands_and_returns_after_end_show(config):
    reports = [rep("A")] + [rep("A")] * 100
    eng = Engine(config=config, episode=EP,
                 plugin_classes=[SqliteTarget, LiveRecorder, FileRecorder],
                 poller=lambda: reports.pop(0), artwork=lambda t, a: None)
    eng.submit({"cmd": "hello"})
    eng.submit({"cmd": "end_show"})
    eng.run(0.01)
    assert eng.snapshot()["phase"] == "ended"
    assert FileRecorder.constructed == 1


def flaky_sqlite():
    """A SqliteTarget whose first construction fails, as if the db were locked."""
    calls = [0]

    class Flaky(SqliteTarget):
        def __init__(self, *args):
            calls[0] += 1
            if calls[0] == 1:
                raise sqlite3.OperationalError("database is locked")
            super().__init__(*args)
    Flaky.__name__ = "SqliteTarget"
    return Flaky


def _sqlite_state(eng):
    return [p for p in eng.snapshot()["plugins"] if p["name"] == "SqliteTarget"][0]


def test_failed_sqlite_retried_on_next_dispatch(config):
    eng = make(config, [rep("A")], classes=(flaky_sqlite(), LiveRecorder))
    assert _sqlite_state(eng)["enabled"] is False
    assert "database is locked" in eng.snapshot()["lastError"]
    eng.tick()
    assert rows(config) == [("A",)]
    assert _sqlite_state(eng)["enabled"] is True
    assert eng.snapshot()["lastError"] is None
    assert eng.snapshot()["currentRowid"] is not None


def test_toggling_failed_sqlite_retries_it(config):
    eng = make(config, [rep("A")], classes=(flaky_sqlite(), LiveRecorder))
    eng.handle({"cmd": "toggle_plugin", "name": "SqliteTarget"})
    assert _sqlite_state(eng)["enabled"] is True
    assert eng.snapshot()["lastError"] is None
    eng.handle({"cmd": "toggle_plugin", "name": "SqliteTarget"})
    assert "cannot be turned off" in eng.snapshot()["lastError"]
    assert _sqlite_state(eng)["enabled"] is True
    eng.tick()
    assert rows(config) == [("A",)]


def test_restart_pushes_current_track_to_live_plugins(config):
    a = make(config, [rep("A")])
    a.tick()
    seen = []

    class Watch(LiveRecorder):
        def logTrack(self, track, startTime):
            seen.append((track.title, len(rows(config))))
    make(config, [], classes=(SqliteTarget, Watch, FileRecorder))
    assert seen == [("A", 1)]
    assert rows(config) == [("A",)]
