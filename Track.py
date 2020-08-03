from dataclasses import dataclass

import os

@dataclass
class Track:
    title: str
    artist: str
    album: str
    length: str
    artwork: str
    artworkFilePath: str
    artworkBaseURL: str
    uniqueId: str
    ignore: bool


    def getArtworkPath(self):
        unglobbed = os.path.expanduser(self.artworkFilePath) 

        if(not unglobbed.endswith("/")):
            unglobbed += "/"

        return f"{unglobbed}{self.artwork}"

    def getArtworkURL(self):
        if(not self.artworkBaseURL.endswith("/")):
            self.artworkBaseURL += "/"

        return f"{self.artworkBaseURL}{self.artwork}"

