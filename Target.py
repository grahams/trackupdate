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

import os
import datetime
import logging
from datetime import date

class Target(object):
    pluginName = "Base Class"
    episodeDate = datetime.datetime.now()
    priority = 0
    logger = logging.getLogger("target base class")
        

    # by default, plugins are not triggered in "archive" mode where we read
    # from the db.  Plugins have to ask to be included by setting this true
    enableArchive = False  

    def __init__(self, config, episode, episodeDate):
        print("If this were a real plugin we would do some initalization here")

    def close(self):
        print("If this were a real plugin we would do some destruction here")

    def logTrack(self, track, startTime):
        print("If this were a real plugin it would do something profound with this data:")

        print("title: " + track.title)
        print("artist: " + track.artist)
        print("album: " + track.album)
        print("length: " + track.length)
        print("id: " + track.uniqueId)
        print("artwork: " + track.artwork)

    def getLongDate(self):
        text = ""

        # compute the suffix
        day = self.episodeDate.day
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = ["st", "nd", "rd"][day % 10 - 1]

        text = ('{dt:%B} {dt.day}' + suffix + ', {dt.year}').format(dt=self.episodeDate)

        return text

    def getTimeStamp(self, tDelta):
        d = {"D": tDelta.days}
        hours, rem = divmod(tDelta.seconds, 3600)
        minutes, seconds = divmod(rem, 60)

        padH = "{:02d}".format(hours)
        padM = "{:02d}".format(minutes)
        padS = "{:02d}".format(seconds)

        return f"{padH}:{padM}:{padS}"

    def getEpisodeTitle(self, episodeNumber):
        return f"Episode {episodeNumber} - {self.getLongDate()}"

    def logToFile(self, fh, text):
        fh.write(text)

        fh.flush()
        os.fsync(fh.fileno())

