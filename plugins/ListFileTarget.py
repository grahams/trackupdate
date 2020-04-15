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

import time
import datetime
from datetime import date

class ListFileTarget(Target):
    pluginName = "List File Writer"
    episodeNumber = "XX"

    filePath = ""
    archiveURL = ""

    wikiFile = None
    blogFile = None
    trackListFile = None

    initialTime = None
    
    def __init__(self, config, episode):
        self.episodeNumber = episode

        # read config entries
        try:
            self.filePath = config.get('ListFileTarget', 'filePath')
            self.archiveURL = config.get('ListFileTarget', 'archiveURL')
        except ConfigParser.NoSectionError:
            print("ListFileTarget: No [ListFileTarget] section in config")
            return
        except ConfigParser.NoOptionError:
            print("ListFileTarget: Missing values in config")
            return

        # if I gave a shit about non-unix platforms I might
        # try to use the proper path sep here. exercise left 
        # for the reader.
        if(self.filePath.endswith("/") != True):
            self.filePath += "/"

        self.filePath = os.path.expanduser(self.filePath)

        self.archiveURL = date.today().strftime(self.archiveURL)

        fileDate = '{dt:%Y}{dt:%m}{dt:%d}'.format(dt=datetime.datetime.now())

        self.initWikiFile(config, episode, fileDate)
        self.initBlogFile(config, episode, fileDate)
        self.initTrackListFile(config, episode, fileDate)

    def initWikiFile(self, config, episode, fileDate):
        headerText = ""

        headerText += "\n\n=== "

        if(self.archiveURL != ""):
            headerText += "[" + self.archiveURL + " "

        headerText += "Show #" + self.episodeNumber + " - "

        headerText += self.createLongDate()

        if(self.archiveURL != ""):
            headerText += "]"

        headerText += " ===\n"

        headerText += "{| border=1 cellspacing=0 cellpadding=5\n"
        headerText += "|'''Song'''\n"
        headerText += "|'''Artist'''\n"
        headerText += "|'''Album'''\n"
        headerText += "|-\n"

        self.wikiFile = open(self.filePath + fileDate + "-wiki.txt", 'w+')
        self.logToFile(self.wikiFile, headerText)

        return

    def initBlogFile(self, config, episode, fileDate):
        headerText = "Subject: " + self.createLongDate() + "\n"
        headerText += "Archive URL: " + self.archiveURL + "\n"
        headerText += "---\n"

        headerText += '<table border="1" cellspacing="0" cellpadding="5">'

	headerText += "<tbody>"

	headerText += "<tr>"
	headerText += "<td><b>Song</b></td>"
	headerText += "<td><b>Artist</b></td>"
	headerText += "<td><b>Album</b></td>"
	headerText += "</tr>"

        self.blogFile = open(self.filePath + fileDate + "-blog.txt", 'w+')
        self.logToFile(self.blogFile, headerText)

        return

    def initTrackListFile(self, config, episode, fileDate):
        self.trackListFile = open(self.filePath + fileDate + "-list.txt", 'w+')
        return

    def logTrack(self, title, artist, album, length, startTime):
        if(self.initialTime == None):
            self.initialTime = time.time()

        self.logWikiTrack(title, artist, album, length, startTime)
        self.logBlogTrack(title, artist, album, length, startTime)
        self.logTrackListTrack(title, artist, album, length, startTime)
        return

    def logWikiTrack(self, title, artist, album, length, startTime):
        trackText = "|" + title + '\n'
    	trackText += "|" + artist + '\n'
    	trackText += "|" + album + '\n'
    	trackText += "|-\n"

        self.logToFile(self.wikiFile, trackText)

        return

    def logBlogTrack(self, title, artist, album, length, startTime):
        trackText = "<tr>"
        trackText += "<tr>"
        trackText += "<td>" + title + "</td>"
        trackText += "<td>" + artist + "</td>"
        trackText += "<td>" + album + "</td>"
        trackText += "</tr>"

        self.logToFile(self.blogFile, trackText)
        return

    def logTrackListTrack(self, title, artist, album, length, startTime):
        # compute the time since the start of the show
        tDelta = str(datetime.timedelta(seconds=round(time.time() -
                                                 self.initialTime)))

        trackText = artist 
        trackText += " - " + title 
        trackText += " - " + tDelta + "\n"

        self.logToFile(self.trackListFile, trackText)

        return

    def close(self):
        fileDate = '{dt:%Y}{dt:%m}{dt:%d}'.format(dt=datetime.datetime.now())

        print("Creating List Files...")

        self.closeWikiFile(fileDate)
        self.closeBlogFile(fileDate)
        self.closeTrackListFile(fileDate)

    def closeWikiFile(self, fileDate):
        self.logToFile(self.wikiFile, "|}" )
        self.wikiFile.close()

        return

    def closeBlogFile(self, fileDate):
        self.logToFile(self.blogFile, "</tbody>")
        self.logToFile(self.blogFile, "</table>")

        self.blogFile.close()
	
        return

    def closeTrackListFile(self, fileDate):
        self.trackListFile.close()

        return

    def createLongDate(self):
        text = ""

        # compute the suffix
        day = date.today().day
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = ["st", "nd", "rd"][day % 10 - 1]

        text = ('{dt:%B} {dt.day}' + suffix + ', {dt.year}').format(dt=datetime.datetime.now())

        return text

    def logToFile(self, fh, text):
        fh.write(text)

        fh.flush()
        os.fsync(fh.fileno())
