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
import datetime

import csv

from datetime import date

class UTCsvFileTarget(Target):
    pluginName = "UT CSV File Writer"
    enableArchive = True
    episodeNumber = None

    filePath = ""

    trackCount = 0
    initialTime = None

    logger = logging.getLogger("UT CSV updater")

    def __init__(self, config, episode, episodeDate):
        self.episodeNumber = episode
        if(episodeDate):
            self.episodeDate = episodeDate
        
        # read config entries
        try:
            self.filePath = config.get('ListCommon', 'filePath')
        except configparser.NoSectionError:
            logging.error("ListCommon: No [ListCommon] section in config")
            return
        except configparser.NoOptionError:
            logging.error("ListCommon: Missing values in config")
            return

        # if I gave a shit about non-unix platforms I might
        # try to use the proper path sep here. exercise left 
        # for the reader.
        if(self.filePath.endswith("/") != True):
            self.filePath += "/"

        self.filePath = os.path.expanduser(self.filePath)

        fileDate = '{dt:%Y}{dt:%m}{dt:%d}'.format(dt=self.episodeDate)
        fullFilePath = self.filePath + fileDate + ".ut.csv"
        showYear = '{dt:%Y}'.format(dt=self.episodeDate)

        self.csvFile = open(fullFilePath, 'w', newline='')
        self.csvWriter = csv.writer(self.csvFile)

        self.csvWriter.writerow(["artist", "title", "timecode"])

        return

    def logTrack(self, track, startTime):
        if(startTime == -1):
            startTime = datetime.datetime.now()

        if(self.initialTime == None):
            self.initialTime = startTime

        tDelta = startTime - self.initialTime
        
        minutes = int(tDelta.total_seconds() / 60)
        seconds = int(tDelta.total_seconds() % 60)

        self.csvWriter.writerow([track.artist, track.title,
                                 f'{minutes:02}:{seconds:02}' ])

        return

    def close(self):
        print("Closing UTCsv File...")

        self.csvFile.close()

        return

