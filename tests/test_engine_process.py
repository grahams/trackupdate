"""Integration tests: the engine as a detached process behind a Unix socket."""
import json
import os
import shutil
import signal
import socket
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time

import pytest

import launcher
import runtime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAKE_GRABBER = os.path.join(REPO, "tests", "fixtures", "fake_grabber.py")


@pytest.fixture
def env(monkeypatch, tmp_path):
    # AF_UNIX paths are limited to ~104 bytes on macOS: keep the runtime dir short.
    run_dir = tempfile.mkdtemp(dir="/tmp", prefix="tu-")
    home = tmp_path / "home"
    home.mkdir()
    db_path = tmp_path / "show.sqlite"
    (home / ".trackupdaterc").write_text(
        "[trackupdate]\npollTime: 1\n\n"
        f"[SqliteTarget]\nenabled: True\ndbPath: {db_path}\n")
    report_file = tmp_path / "report.json"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("TRACKUPDATE_RUNTIME_DIR", run_dir)
    monkeypatch.setenv("FAKE_GRABBER_FILE", str(report_file))
    # Make the iTunes artwork lookup fail fast instead of touching the network.
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        monkeypatch.setenv(var, "http://127.0.0.1:9")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)

    pids = []
    real_popen = subprocess.Popen

    def recording_popen(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        pids.append(proc.pid)
        return proc

    # Record every engine spawned, even when ensure_engine then fails.
    monkeypatch.setattr(launcher.subprocess, "Popen", recording_popen)

    class Env:
        db = db_path

        def start(self, episode="900"):
            launcher.ensure_engine(episode, grabber=FAKE_GRABBER)
            return runtime.read_info()["pid"]

        def play(self, track_id, title, artist="Artist"):
            tmp = report_file.with_suffix(".tmp")
            tmp.write_text(json.dumps({
                "trackId": track_id, "trackName": title, "trackArtist": artist,
                "trackAlbum": "Album", "trackLength": "3:00"}))
            os.replace(tmp, report_file)

    yield Env()

    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        _wait_exit(pid, 5)
    shutil.rmtree(run_dir, ignore_errors=True)


def _exited(pid):
    try:
        done, _ = os.waitpid(pid, os.WNOHANG)
        return done == pid
    except ChildProcessError:  # not our child, or already reaped
        try:
            os.kill(pid, 0)
            return False
        except ProcessLookupError:
            return True


def _wait_exit(pid, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _exited(pid):
            return True
        time.sleep(0.05)
    return False


def _connect():
    s = socket.socket(socket.AF_UNIX)
    s.settimeout(5)
    s.connect(str(runtime.socket_path()))
    return s


def _send(s, msg):
    s.sendall(runtime.encode(msg))


def _wait_snapshot(s, pred, timeout=5):
    deadline = time.monotonic() + timeout
    buf = b""
    while time.monotonic() < deadline:
        s.settimeout(max(0.01, deadline - time.monotonic()))
        try:
            chunk = s.recv(65536)
        except TimeoutError:
            break
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            snap = runtime.decode(line)
            if pred(snap):
                return snap
    raise AssertionError("no matching snapshot")


def _titles(snap):
    return [t["title"] for t in snap["tracks"]]


def _db_titles(db):
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    try:
        return [r[0] for r in conn.execute(
            "SELECT title FROM trackupdate ORDER BY rowid")]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _wait_for(pred, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(0.1)
    return False


def test_engine_logs_track_and_serves_snapshot(env):
    env.start("900")
    env.play("id-1", "First Song")
    s = _connect()
    try:
        _send(s, {"cmd": "hello"})
        snap = _wait_snapshot(s, lambda m: "First Song" in _titles(m))
        assert snap["episode"] == "900"
        assert snap["phase"] == "live"
    finally:
        s.close()


def test_engine_survives_client_disconnect(env):
    env.start("900")
    env.play("id-1", "First Song")
    assert _wait_for(lambda: _db_titles(env.db) == ["First Song"])

    # Garbage, an unterminated line, then an abrupt reset.
    s = _connect()
    s.sendall(b"not json\n\xff\xfe\n[1, 2]\n{\"cmd\": ")
    s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    s.close()
    # A client that never reads.
    stalled = _connect()

    env.play("id-2", "Second Song")
    assert _wait_for(lambda: _db_titles(env.db) == ["First Song", "Second Song"])

    s = _connect()
    try:
        _send(s, {"cmd": "hello"})
        snap = _wait_snapshot(s, lambda m: "Second Song" in _titles(m))
        assert snap["phase"] == "live"
    finally:
        s.close()
        stalled.close()


def test_ensure_engine_attaches_to_same_episode(env):
    pid = env.start("900")
    assert env.start("900") == pid


def test_second_episode_refused(env):
    env.start("900")
    with pytest.raises(launcher.EngineBusy) as exc:
        launcher.ensure_engine("901", grabber=FAKE_GRABBER)
    assert exc.value.episode == "900"


def test_engine_main_refuses_when_one_is_running(env):
    env.start("900")
    p = subprocess.run(
        [sys.executable, os.path.join(REPO, "engine.py"), "-e", "901",
         "--grabber", FAKE_GRABBER],
        capture_output=True, text=True, timeout=10, cwd=REPO)
    assert p.returncode == 1
    assert "900" in p.stderr


def test_end_show_over_socket_removes_runtime(env):
    pid = env.start("900")
    env.play("id-1", "First Song")
    assert _wait_for(lambda: _db_titles(env.db) == ["First Song"])
    s = _connect()
    try:
        _send(s, {"cmd": "end_show"})
        snap = _wait_snapshot(s, lambda m: m["phase"] == "ended", timeout=10)
        assert snap["results"] == []
    finally:
        s.close()
    assert _wait_exit(pid, 10)
    assert not runtime.socket_path().exists()
    assert not runtime.info_path().exists()


def test_sigterm_ends_show(env):
    pid = env.start("900")
    os.kill(pid, signal.SIGTERM)
    assert _wait_exit(pid, 10)
    assert not runtime.socket_path().exists()
    assert "Closing database" in runtime.log_path().read_text()


def test_start_failure_reports_log_tail(env, monkeypatch):
    monkeypatch.setattr(launcher, "ENGINE_SCRIPT",
                        os.path.join(REPO, "tests", "no_such_engine.py"))
    with pytest.raises(launcher.EngineStartFailed) as exc:
        launcher.ensure_engine("900", grabber=FAKE_GRABBER)
    assert "no_such_engine.py" in str(exc.value)
