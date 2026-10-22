"""On-disk files and wire framing shared by the engine and TUI processes."""
import json
import os
import socket
import tempfile
from dataclasses import asdict
from pathlib import Path

from session import OverrideState
from Track import Track


def runtime_dir() -> Path:
    d = Path(os.environ.get("TRACKUPDATE_RUNTIME_DIR") or Path.home() / ".trackupdate")
    d.mkdir(parents=True, exist_ok=True)
    return d


def socket_path() -> Path:
    return runtime_dir() / "engine.sock"


def info_path() -> Path:
    return runtime_dir() / "engine.json"


def override_path() -> Path:
    return runtime_dir() / "override.json"


def log_path() -> Path:
    return runtime_dir() / "engine.log"


def _write_atomic(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write_info(episode: str, pid: int) -> None:
    _write_atomic(info_path(), json.dumps({"episode": episode, "pid": pid}))


def read_info() -> dict | None:
    try:
        return json.loads(info_path().read_text())
    except (OSError, ValueError):
        return None


def clear_runtime() -> None:
    for p in (socket_path(), info_path(), override_path()):
        p.unlink(missing_ok=True)


def engine_alive() -> dict | None:
    info = read_info()
    if info is not None:
        try:
            os.kill(info["pid"], 0)
            s = socket.socket(socket.AF_UNIX)
            try:
                s.settimeout(1.0)
                s.connect(str(socket_path()))
            finally:
                s.close()
            return info
        except (OSError, KeyError, TypeError):
            pass
    clear_runtime()
    return None


def save_override(state: OverrideState, last_report: dict | None) -> None:
    _write_atomic(override_path(), json.dumps({
        "track": asdict(state.track),
        "swinsian_idle": state.swinsian_idle,
        "last_report": last_report,
    }))


def load_override() -> tuple[OverrideState, dict | None] | None:
    try:
        d = json.loads(override_path().read_text())
        state = OverrideState(Track(**d["track"]), bool(d["swinsian_idle"]))
        return state, d.get("last_report")
    except (OSError, ValueError, KeyError, TypeError):
        return None


def clear_override() -> None:
    override_path().unlink(missing_ok=True)


def encode(msg: dict) -> bytes:
    return json.dumps(msg).encode("utf-8") + b"\n"


def decode(line: bytes) -> dict:
    return json.loads(line.decode("utf-8"))
