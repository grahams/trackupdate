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


def clear_stale() -> None:
    """Remove the socket and info files but keep any persisted override."""
    for p in (socket_path(), info_path()):
        p.unlink(missing_ok=True)


def clear_runtime() -> None:
    clear_stale()
    override_path().unlink(missing_ok=True)


def engine_alive() -> dict | None:
    """Return the running engine's info, or None.

    Stale files are cleared only when engine.json names a dead pid. With no
    info, or a live pid whose socket isn't accepting yet, an engine may be
    starting (it binds before writing info), so nothing is deleted.
    """
    info = read_info()
    if info is None:
        return None
    try:
        os.kill(info["pid"], 0)
    except ProcessLookupError:
        clear_stale()
        return None
    except PermissionError:
        pass  # pid exists but belongs to someone else
    except (KeyError, TypeError, ValueError, OverflowError):
        clear_stale()  # malformed info: nothing can be running behind it
        return None
    s = socket.socket(socket.AF_UNIX)
    try:
        s.settimeout(1.0)
        s.connect(str(socket_path()))
        return info
    except OSError:
        return None
    finally:
        s.close()


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
