from dataclasses import dataclass

@dataclass
class Track:
    title: str
    artist: str
    album: str
    length: str
    artwork: str
    uniqueId: str
    ignore: bool

