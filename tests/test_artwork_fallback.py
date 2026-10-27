import configparser
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugins"))

from AudioHijackTarget import AudioHijackTarget
from CsvFileTarget import CsvFileTarget
from Track import Track


@pytest.fixture
def config(tmp_path):
    config = configparser.ConfigParser()
    config.read_dict({
        "trackupdate": {"coverImagePath": str(tmp_path / "covers"),
                        "stopArtwork": "stop.jpg"},
        "ListCommon": {"filePath": str(tmp_path), "showTitle": "Show",
                       "showArtist": "Host"},
        "AudioHijackTarget": {"initTitle": "t", "initArtist": "a",
                              "initAlbum": "al", "initTime": "0:00",
                              "initDestination": str(tmp_path / "NowPlaying.txt")},
    })
    (tmp_path / "covers").mkdir()
    return config


@pytest.mark.parametrize("cls", [CsvFileTarget, AudioHijackTarget])
@pytest.mark.parametrize("url", [None, ""])
def test_missing_artwork_url_uses_stop_artwork(config, tmp_path, cls, url):
    # rows from the db can carry NULL or '' artworkUrl; neither may be fetched
    plugin = cls(config, 7, datetime(2026, 1, 1, 10, 0, 0))
    track = Track(title="One", artist="A", album="Al", length="1:00",
                  artworkURL=url, uniqueId="u1", ignore=False)
    plugin.logTrack(track, datetime(2026, 1, 1, 10, 0, 0))
    plugin.close()
    assert list((tmp_path / "covers").iterdir()) == []
