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
import logging

import time

from datetime import datetime

class TrackListFileTarget(Target):
    logger = logging.getLogger("track list updater")
    pluginName = "Track List File Writer"
    enableArchive = True

    filePath = ""

    trackListFile = None

    initialTime = None
    
    def __init__(self, config, episode, episodeDate):
        if(episodeDate):
            self.episodeDate = episodeDate
        
        # read config entries
        try:
            self.filePath = config.get('ListCommon', 'filePath')
        except configparser.NoSectionError:
            self.logger.error("ListCommon: No [ListCommon] section in config")
            return
        except configparser.NoOptionError:
            self.logger.error("ListCommon: Missing values in config")
            return

        # if I gave a shit about non-unix platforms I might
        # try to use the proper path sep here. exercise left 
        # for the reader.
        if(self.filePath.endswith("/") != True):
            self.filePath += "/"

        self.filePath = os.path.expanduser(self.filePath)

        fileDate = '{dt:%Y}{dt:%m}{dt:%d}'.format(dt=self.episodeDate)

        self.trackListFile = open(self.filePath + fileDate + "-list.txt", 'w+')
        return

    def logTrack(self, track, startTime):
        if(startTime == -1):
            startTime = datetime.now()

        if(self.initialTime == None):
            self.initialTime = startTime

        if( track.ignore is not True):
            # compute the time since the start of the show
            tDelta = startTime - self.initialTime
            tFormat = self.getTimeStamp(tDelta)
            
            trackText = f"{track.artist} - {track.title} ({tFormat})\n"

            self.logToFile(self.trackListFile, trackText)

        return

    def close(self):
        print("Closing Track List File...")

        self.trackListFile.close()

        return
