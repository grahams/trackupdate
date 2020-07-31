# Copyright (c) 2020 Sean M. Graham <www.sean-graham.com>
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

import os
import sys
import configparser

import time
import datetime
from datetime import date

class CueFileTarget(Target):
    pluginName = "Cue File Writer"
    showArtist = ""

    filePath = ""

    cueFile = None

    trackCount = 0
    initialTime = None

    def __init__(self, config, episode):
        # read config entries
        try:
            self.filePath = config.get('ListCommon', 'filePath')
            self.showArtist = config.get('ListCommon', 'showArtist')
        except configparser.NoSectionError:
            print("ListCommon: No [ListCommon] section in config")
            return
        except configparser.NoOptionError:
            print("ListCommon: Missing values in config")
            return

        # if I gave a shit about non-unix platforms I might
        # try to use the proper path sep here. exercise left 
        # for the reader.
        if(self.filePath.endswith("/") != True):
            self.filePath += "/"

        self.filePath = os.path.expanduser(self.filePath)

        fileDate = '{dt:%Y}{dt:%m}{dt:%d}'.format(dt=datetime.datetime.now())

        headerText = "REM GENRE Rock\n"
        headerText += 'REM DATE {dt:%Y}\n'.format(dt=datetime.datetime.now())
        headerText += f'PERFORMER "{self.showArtist}"\n'
        headerText += f'TITLE "{self.createLongDate()}"\n'
        headerText += f'FILE "{fileDate}.mp3" MP3\n'

        self.cueFile = open(self.filePath + fileDate + ".cue", 'w+')
        self.logToFile(self.cueFile, headerText)

        return

    def logTrack(self, track, startTime):
        if(self.initialTime == None):
            self.initialTime = time.time()

        if( track.ignore is not True):
            # compute the time since the start of the show
            tDelta = datetime.timedelta(seconds=round(time.time() -
                                                    self.initialTime))

            minutes = int(tDelta.total_seconds() / 60)
            seconds = int(tDelta.total_seconds() % 60)

            self.trackCount += 1

            trackText = (f"  TRACK {self.trackCount:02} AUDIO\n"
                        f'    TITLE "{track.title}"\n'
                        f'    PERFORMER "{track.artist}"\n'
                        f'    INDEX 01 {minutes:02}:{seconds:02}:00\n')

            self.logToFile(self.cueFile, trackText)

        return

    def close(self):
        print("Closing Cue File...")

        self.cueFile.close()

        return

