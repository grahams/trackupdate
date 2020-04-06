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
import ConfigParser
import os

class AudioHijackTarget(Target):
    pluginName = "Audio Hijack Track Updater"

    initDestination = "~/Library/Application Support/Audio Hijack/NowPlaying.txt"
    initTitle = ""
    initArtist = ""
    initAlbum = ""
    initTime = ""

    def __init__(self, config, episode):
        try:
            self.initTitle = config.get('AudioHijackTarget', 'initTitle')
            self.initArtist = config.get('AudioHijackTarget', 'initArtist')
            self.initAlbum = config.get('AudioHijackTarget', 'initAlbum')
            self.initTime = config.get('AudioHijackTarget', 'initTime')
            self.initDestination = config.get('AudioHijackTarget', 'initDestination')
        except ConfigParser.NoSectionError:
            print("AudioHijackTarget: No [AudioHijackTarget] section in config")
            return
        except ConfigParser.NoOptionError:
            print("AudioHijackTarget: Missing values in config")
            return

        self.initDestination = os.path.expanduser(self.initDestination)
        fh = open(self.initDestination, 'w')
        fh.write("Title: " + self.initTitle + '\n')
        fh.write("Artist: " + self.initArtist + '\n')
        fh.write("Album: " + self.initAlbum + '\n')
        fh.write("Time: " + self.initTime + '\n')
        fh.write("Destination: " + self.initDestination + '\n')
        fh.close()

    def close(self):
        os.remove(self.initDestination)

    def logTrack(self, title, artist, album, time, startTime):
        fh = open(self.initDestination, 'w')
        fh.write("Title: " + title + '\n')
        fh.write("Artist: " + artist + '\n')
        fh.write("Album: " + album + '\n')
        fh.write("Time: " + time + '\n')
        fh.close()
