import uuid

from Track import Track
from session import Session


def rep(title, artist="X", id="1", album="Alb", length="100"):
    return {"trackName": title, "trackArtist": artist, "trackAlbum": album,
            "trackLength": length, "trackId": id}


STOP = Track("Stop", "Me", "", "0", None, "stop", False)


def make(**kw):
    kw.setdefault("ignore_album", None)
    kw.setdefault("intro_album", "")
    kw.setdefault("stop_track", None)
    return Session(**kw)


def test_first_track_dispatched():
    s = make()
    t = s.on_poll(rep("A"))
    assert t.title == "A" and t.artist == "X" and t.uniqueId == "1"
    assert t.artworkURL is None and t.ignore is False
    assert s.current is t and s.source == "swinsian"


def test_same_report_not_redispatched():
    s = make()
    assert s.on_poll(rep("A")) is not None
    assert s.on_poll(rep("A")) is None


def test_intro_album_waits_then_starts():
    s = make(intro_album="Heartbeat")
    assert s.on_poll(rep("Intro", album="Heartbeat")) is None
    assert s.on_poll({}) is None
    t = s.on_poll(rep("Real", id="2"))
    assert t.title == "Real"


def test_empty_report_gives_stop_track_when_configured():
    s = make(stop_track=STOP, started=True)
    s.on_poll(rep("A"))
    t = s.on_poll({})
    assert t == STOP and t is not STOP
    assert s.source == "stop"
    t.title = "mutated"
    assert STOP.title == "Stop"


def test_empty_report_none_without_stop_values():
    s = make(started=True)
    s.on_poll(rep("A"))
    assert s.on_poll({}) is None


def test_ignore_album_sets_ignore():
    s = make(ignore_album="Skip")
    assert s.on_poll(rep("A", album="Skip")).ignore is True
    assert s.on_poll(rep("B", id="2")).ignore is False


def test_restart_dedupes_by_unique_id():
    cur = Track("Killing Moon", "X", "Alb", "1", None, "77", False)
    s = make(current=cur, started=True, last_report=None)
    assert s.on_poll(rep("Teh Killing Moon", id="77")) is None


def test_dedupe_by_artist_title_when_no_id():
    cur = Track("A", "X", "Alb", "1", None, "", False)
    s = make(current=cur, started=True)
    assert s.on_poll(rep("A", id="")) is None


def _overridden(**kw):
    s = make(**kw)
    s.on_poll(rep("A"))
    s.set_override("Manual", "Me", "Alb", "5")
    return s


def test_none_report_changes_nothing_during_override():
    s = _overridden()
    for _ in range(3):
        assert s.on_poll(None) is None
    assert s.on_poll(rep("A")) is None
    assert s.override is not None and s.override.swinsian_idle is False


def test_override_ignores_muted_advance():
    s = _overridden()
    assert s.on_poll(rep("B", id="2")) is None
    assert s.override is not None


def test_override_pause_then_resume_same_track_logs_it():
    s = _overridden(stop_track=STOP)
    assert s.on_poll({}) is None
    t = s.on_poll(rep("A"))
    assert t.title == "A"
    assert s.override is None and s.source == "swinsian"


def test_override_set_while_stopped_ends_on_play():
    s = make(started=True, last_report={})
    s.set_override("Manual", "Me", "Alb", "5")
    assert s.override.swinsian_idle is True
    assert s.on_poll(rep("C", id="3")).title == "C"
    assert s.override is None


def test_override_unique_id_is_uuid():
    s = make()
    t = s.set_override("Manual", "Me", "Alb", "5")
    uuid.UUID(t.uniqueId)
    assert s.current is t and s.source == "override"


def test_override_ignore_album():
    s = make(ignore_album="Skip")
    assert s.set_override("M", "Me", "Skip", "5").ignore is True


def test_cancel_override_waits_for_next_change():
    s = _overridden()
    s.cancel_override()
    assert s.override is None
    assert s.on_poll(rep("A")) is None
    assert s.on_poll(rep("B", id="2")).title == "B"


def test_refresh_adopts_new_tags_for_same_track():
    s = make(ignore_album="Bumpers")
    s.on_poll(rep("Tpyo"))
    assert s.on_poll(rep("Typo", album="Bumpers")) is None  # same id: deduped
    t = s.refresh_current()
    assert (t.title, t.album, t.ignore) == ("Typo", "Bumpers", True)
    assert s.current is t
    assert s.refresh_current() is None  # nothing new


def test_refresh_ignores_other_track_and_override():
    s = make()
    s.on_poll(rep("A"))
    s.last_report = rep("B", id="2")
    assert s.refresh_current() is None
    s.last_report = rep("A2")
    s.set_override("Live", "Guest", "", "")
    assert s.refresh_current() is None
