"""trackupdate.py's live-mode wiring."""
import sys

import pytest

import launcher
import trackupdate


def test_missing_tui_fails_before_starting_an_engine(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(launcher, "ensure_engine",
                        lambda *a, **k: calls.append((a, k)) or True)
    monkeypatch.setitem(sys.modules, "tui", None)  # import tui -> ImportError

    with pytest.raises(SystemExit) as exc:
        trackupdate.TrackUpdate(["-e", "900"])

    assert exc.value.code not in (0, None)
    assert calls == []
    err = capsys.readouterr().err
    assert "Can't load the TUI" in err and "--plain" in err
