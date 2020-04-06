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

import datetime
from datetime import date

class ListFileTarget(Target):
    pluginName = "List File Writer"
    episodeNumber = "XX"

    filePath = ""
    archiveURL = ""

    wikiFileContents = ""
    blogFileContents = ""
    trackListContents = ""
    
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

        self.initWikiFile(config, episode)
        self.initBlogFile(config, episode)
        self.initTracklistFile(config, episode)

    def initWikiFile(self, config, episode):
        text = ""

        text += "\n\n=== "

        if(self.archiveURL != ""):
            text += "[" + self.archiveURL + " "

        text += "Show #" + self.episodeNumber + " - "

        text += self.createLongDate()

        if(self.archiveURL != ""):
            text += "]"

        text += " ===\n"

        text += "{| border=1 cellspacing=0 cellpadding=5\n"
        text += "|'''Song'''\n"
        text += "|'''Artist'''\n"
        text += "|'''Album'''\n"
        text += "|-\n"

        self.wikiFileContents = text

        return

    def initBlogFile(self, config, episode):
        self.blogFileContents = "Subject: " + self.createLongDate() + "\n"
        self.blogFileContents += "Archive URL: " + self.archiveURL + "\n"
        self.blogFileContents += "---\n"

        self.blogFileContents += '<table border="1" cellspacing="0" cellpadding="5">'
	
	self.blogFileContents += "<tbody>"

	self.blogFileContents += "<tr>"
	self.blogFileContents += "<td><b>Song</b></td>"
	self.blogFileContents += "<td><b>Artist</b></td>"
	self.blogFileContents += "<td><b>Album</b></td>"
	self.blogFileContents += "</tr>"

        return

    def initTracklistFile(self, config, episode):
        return

    def logTrack(self, title, artist, album, time, startTime):
        self.logWikiTrack(title, artist, album, time, startTime)
        self.logBlogTrack(title, artist, album, time, startTime)
        self.logTracklistTrack(title, artist, album, time, startTime)
        return

    def logWikiTrack(self, title, artist, album, time, startTime):
        self.wikiFileContents += "|" + title + '\n'
    	self.wikiFileContents += "|" + artist + '\n'
    	self.wikiFileContents += "|" + album + '\n'
    	self.wikiFileContents += "|-\n"

        return

    def logBlogTrack(self, title, artist, album, time, startTime):
        self.blogFileContents += "<tr>"
        self.blogFileContents += "<td>" + title + "</td>"
        self.blogFileContents += "<td>" + artist + "</td>"
        self.blogFileContents += "<td>" + album + '</td>'
        self.blogFileContents += "</tr>"

        return

    def logTracklistTrack(self, title, artist, album, time, startTime):
        self.trackListContents += artist + " - " + title + "\n"
        return

    def close(self):
        fileDate = '{dt:%Y}{dt:%m}{dt:%d}'.format(dt=datetime.datetime.now())

        print("Creating List Files...")

        self.closeWikiFile(fileDate)
        self.closeBlogFile(fileDate)
        self.closeTracklistFile(fileDate)

    def closeWikiFile(self, fileDate):
	self.wikiFileContents += "|}"

        fh = open(self.filePath + fileDate + "-wiki.txt", 'w+')

        fh.write(self.wikiFileContents)
        fh.close()

        return

    def closeBlogFile(self, fileDate):
        self.blogFileContents += "</tbody>"
        self.blogFileContents += "</table>"

        fh = open(self.filePath + fileDate + "-blog.txt", 'w+')

        fh.write(self.blogFileContents)
        fh.close()
	
        return

    def closeTracklistFile(self, fileDate):
        fh = open(self.filePath + fileDate + "-list.txt", 'w+')

        fh.write(self.trackListContents)
        fh.close()

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
