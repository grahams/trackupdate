"""Start the detached engine process, or find the one already running."""
import os
import subprocess
import sys
import threading
import time

import runtime

REPO = os.path.dirname(os.path.abspath(__file__))
ENGINE_SCRIPT = os.path.join(REPO, "engine.py")
START_TIMEOUT = 5.0
LOG_TAIL_LINES = 20


class EngineBusy(Exception):
    def __init__(self, episode):
        super().__init__(f"an engine for episode {episode} is already running")
        self.episode = episode


class EngineStartFailed(Exception):
    pass


def ensure_engine(episode: str, grabber: str | None = None) -> None:
    episode = str(episode)
    info = runtime.engine_alive()
    if info is not None:
        if str(info.get("episode")) == episode:
            return
        raise EngineBusy(str(info.get("episode")))

    cmd = [sys.executable, ENGINE_SCRIPT, "-e", episode]
    if grabber:
        cmd += ["--grabber", os.path.abspath(grabber)]
    with open(runtime.log_path(), "ab") as log:
        proc = subprocess.Popen(cmd, cwd=REPO, start_new_session=True,
                                stdin=subprocess.DEVNULL, stdout=log,
                                stderr=subprocess.STDOUT)
    # Reap the engine whenever it exits so it never lingers as a zombie of a
    # longer-lived caller (the TUI).
    threading.Thread(target=proc.wait, daemon=True, name="engine-reaper").start()

    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        info = runtime.engine_alive()
        if info is not None and info.get("pid") == proc.pid:
            return
        if proc.returncode is not None:
            break
        time.sleep(0.1)

    status = (f"exited with status {proc.returncode}" if proc.returncode is not None
              else f"pid {proc.pid} did not open its socket within {START_TIMEOUT:g} s")
    raise EngineStartFailed(
        f"engine for episode {episode} {status}; last lines of "
        f"{runtime.log_path()}:\n{_log_tail()}")


def _log_tail():
    try:
        lines = runtime.log_path().read_text(errors="replace").splitlines()
    except OSError:
        return "(no log)"
    return "\n".join(lines[-LOG_TAIL_LINES:])
