import subprocess
import sys

import runtime
from session import OverrideState
from Track import Track


def test_override_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACKUPDATE_RUNTIME_DIR", str(tmp_path))
    track = Track("T", "A", "Al", "120", None, "uid-1", True)
    runtime.save_override(OverrideState(track, swinsian_idle=True), {"title": "x"})
    state, report = runtime.load_override()
    assert state.track == track
    assert state.swinsian_idle is True
    assert report == {"title": "x"}
    runtime.clear_override()
    runtime.clear_override()
    assert runtime.load_override() is None


def test_engine_alive_clears_stale_info(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACKUPDATE_RUNTIME_DIR", str(tmp_path))
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    runtime.write_info("412", p.pid)
    assert runtime.read_info() == {"episode": "412", "pid": p.pid}
    assert runtime.engine_alive() is None
    assert not runtime.info_path().exists()


def test_encode_decode_roundtrip():
    msg = {"type": "state", "n": 1, "s": "é"}
    data = runtime.encode(msg)
    assert data.endswith(b"\n")
    assert runtime.decode(data) == msg
