import requests 
import logging

from dataclasses import dataclass
from pathlib import Path
from os.path import expanduser

@dataclass
class Track:
    title: str
    artist: str
    album: str
    length: str
    artworkURL: str
    uniqueId: str
    ignore: bool
    
    def fetchArtwork(self, coverImagePath):
        logger = logging.getLogger("track base class")
        p = Path(f'{expanduser(coverImagePath)}/{self.uniqueId}.jpg')

        if(p.is_file() == False):
            with p.open(mode='wb') as handle:
                response = requests.get(self.artworkURL, stream=True)

                if not response.ok:
                    return False

                for block in response.iter_content(1024):
                    if not block:
                        return False

                    handle.write(block)
        else:
            logger.debug("Artwork file already exists. Skipping")

        return str(p)
        
