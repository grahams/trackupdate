# Copyright (c) 2010 Sean M. Graham <www.sean-graham.com>
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

from Target import Target
from Track import Track

import configparser
import os
import urllib.parse

class AudioHijackTarget(Target):
    pluginName = "Audio Hijack Track Updater"

    initDestination = "~/Library/Application Support/Audio Hijack/NowPlaying.txt"
    initTitle = ""
    initArtist = ""
    initAlbum = ""
    initTime = ""
    initArtwork = ""
    coverImagePath = ""
    stopArtwork = ""

    def __init__(self, config, episode, episodeDate):
        if(episodeDate):
            self.episodeDate = episodeDate
        
        try:
            self.initTitle = config.get('AudioHijackTarget', 'initTitle')
            self.initArtist = config.get('AudioHijackTarget', 'initArtist')
            self.initAlbum = config.get('AudioHijackTarget', 'initAlbum')
            self.initTime = config.get('AudioHijackTarget', 'initTime')
            self.initDestination = config.get('AudioHijackTarget', 'initDestination')
            self.coverImagePath = config.get('trackupdate', 'coverImagePath')
            self.stopArtwork = config.get('trackupdate', 'stopArtwork')
        except configparser.NoSectionError:
            print("AudioHijackTarget: No [AudioHijackTarget] section in config")
            return
        except configparser.NoOptionError:
            print("AudioHijackTarget: Missing values in config")
            return

        self.initDestination = os.path.expanduser(self.initDestination)
        self.coverImagePath = os.path.expanduser(self.coverImagePath) 

        track = Track(self.initTitle, 
                      self.initArtist, 
                      self.initAlbum,
                      self.initTime,
                      None,
                      "",
                      False)

        self.logTrack(track, None);

    def close(self):
        os.remove(self.initDestination)

    def logTrack(self, track, startTime):
        artworkPath = ""

        if( (track.artworkURL != None) and (self.stopArtwork not in track.artworkURL) ):
            artworkPath = track.fetchArtwork(self.coverImagePath)
        else:
            artworkPath = f"{self.coverImagePath}/{self.stopArtwork}"

        title = track.title or "";
        artist = track.artist or "";
        album = track.album or "";
        length = track.length or "";

        track.title = track.title.replace("-", " ")

        fh = open(self.initDestination, 'w')
        fh.write(f"Title: {title.replace(' - ', '-') }\n")
        fh.write(f"Artist: {artist.replace(' - ', '-')}\n")
        fh.write(f"Album: {album.replace(' - ', '-')}\n")
        fh.write(f"Time: {length.replace(' - ', '-')}\n")
        fh.write(f"Artwork: file://{urllib.parse.quote(artworkPath)}\n")
        fh.close()
