"""Pure state machine deciding which Swinsian polls become dispatched tracks."""
import uuid
from dataclasses import dataclass, replace

from Track import Track


@dataclass
class OverrideState:
    track: Track
    swinsian_idle: bool  # True once Swinsian has reported {} since the override was set


class Session:
    def __init__(self, *, ignore_album, intro_album, stop_track,
                 current=None, override=None, started=False, last_report=None):
        self.ignore_album = ignore_album
        self.intro_album = intro_album
        self.stop_track = stop_track
        self.current = current
        self.override = override
        self.started = started
        self.last_report = last_report
        self.source = None

    def on_poll(self, report):
        if report is None:
            return None

        if not self.started:
            if report == {} or (self.intro_album
                                and report.get("trackAlbum") == self.intro_album):
                self.last_report = report
                return None
            self.started = True

        skip_equality = False
        if self.override is not None:
            if report == {}:
                self.override.swinsian_idle = True
                self.last_report = report
                return None
            if not self.override.swinsian_idle:
                self.last_report = report
                return None
            self.override = None
            skip_equality = True

        if not skip_equality and report == self.last_report:
            return None
        self.last_report = report

        if report == {}:
            if self.stop_track is None:
                return None
            track = replace(self.stop_track)
            source = "stop"
        else:
            track = Track(
                title=report.get("trackName", ""),
                artist=report.get("trackArtist", ""),
                album=report.get("trackAlbum", ""),
                length=report.get("trackLength", ""),
                artworkURL=None,
                uniqueId=report.get("trackId", ""),
                ignore=False,
            )
            source = "swinsian"

        cur = self.current
        if cur is not None:
            if track.uniqueId and track.uniqueId == cur.uniqueId:
                return None
            if (track.artist, track.title) == (cur.artist, cur.title):
                return None

        track.ignore = track.album == self.ignore_album
        self.current = track
        self.source = source
        return track

    def set_override(self, title, artist, album, length):
        track = Track(title=title, artist=artist, album=album, length=length,
                      artworkURL=None, uniqueId=str(uuid.uuid4()),
                      ignore=album == self.ignore_album)
        self.override = OverrideState(
            track, swinsian_idle=self.last_report in (None, {}))
        self.current = track
        self.source = "override"
        self.started = True
        return track

    def cancel_override(self):
        self.override = None
