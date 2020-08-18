# Copyright (c) 2018 Sean T. Hammond
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

class LadioCastTarget(Target):
    pluginName = "LadioCast Track Updater"

    initTitle = ""
    initArtist = ""
    initAlbum = ""
    initTime = ""

    def __init__(self, config, episode, episodeDate):
        try:
            self.initTitle = config.get('LadioCastTarget', 'initTitle')
            self.initArtist = config.get('LadioCastTarget', 'initArtist')
            self.initAlbum = config.get('LadioCastTarget', 'initAlbum')
            self.initTime = config.get('LadioCastTarget', 'initTime')
        except ConfigParser.NoSectionError:
            print("LadioCastTarget: No [LadioCastTarget] section in config")
            return
        except ConfigParser.NoOptionError:
            print("LadioCastTarget: Missing values in config")
            return

    def close(self):
        return

    def logTrack(self, track, startTime):
        theCmd = """osascript -e 'tell application "LadioCast" to set metadata song to "%s - %s"'""" % (track.artist, track.title)

        os.system(theCmd)

