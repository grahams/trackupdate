import os
import subprocess

from track_source import GRABBER_PATH, poll_swinsian


def _returning(value):
    return lambda *a, **k: value


def _raising(exc):
    def run(*a, **k):
        raise exc
    return run


def test_poll_parses_json():
    run = _returning('{"trackName":"A","trackArtist":"B"}')
    assert poll_swinsian(run=run) == {"trackName": "A", "trackArtist": "B"}


def test_poll_empty_object_when_idle():
    assert poll_swinsian(run=_returning("{}")) == {}


def test_poll_none_on_timeout():
    run = _raising(subprocess.TimeoutExpired(cmd="x", timeout=10))
    assert poll_swinsian(run=run) is None


def test_poll_none_on_bad_json():
    assert poll_swinsian(run=_returning("nope")) is None


def test_poll_none_on_nonzero_exit():
    run = _raising(subprocess.CalledProcessError(1, "x"))
    assert poll_swinsian(run=run) is None


def test_grabber_path_is_absolute():
    assert os.path.isabs(GRABBER_PATH)
