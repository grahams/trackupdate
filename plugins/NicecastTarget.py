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

class NicecastTarget(Target):
    nowPlayingFilePath = os.path.expanduser('~/Library/Application Support/Nicecast/NowPlaying.txt')
    pluginName = "Nicecast Track Updater"

    initTitle = ""
    initArtist = ""
    initAlbum = ""
    initTime = ""

    def __init__(self, config, episode):
        try:
            self.initTitle = config.get('NicecastTarget', 'initTitle')
            self.initArtist = config.get('NicecastTarget', 'initArtist')
            self.initAlbum = config.get('NicecastTarget', 'initAlbum')
            self.initTime = config.get('NicecastTarget', 'initTime')
        except ConfigParser.NoSectionError:
            print("NicecastTarget: No [NicecastTarget] section in config")
            return
        except ConfigParser.NoOptionError:
            print("NicecastTarget: Missing values in config")
            return

        fh = open(self.nowPlayingFilePath, 'w')
        fh.write("Title: " + self.initTitle + '\n')
        fh.write("Artist: " + self.initArtist + '\n')
        fh.write("Album: " + self.initAlbum + '\n')
        fh.write("Time: " + self.initTime + '\n')
        fh.close()

    def close(self):
        os.remove(self.nowPlayingFilePath)

    def logTrack(self, title, artist, album, time, startTime):
        fh = open(self.nowPlayingFilePath, 'w')
        fh.write("Title: " + title + '\n')
        fh.write("Artist: " + artist + '\n')
        fh.write("Album: " + album + '\n')
        fh.write("Time: " + time + '\n')
        fh.close()
