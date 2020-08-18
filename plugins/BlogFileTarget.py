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

class BlogFileTarget(Target):
    pluginName = "Blog File Writer"
    enableArchive = True
    showArtist = ""

    episodeNumber = None
    filePath = ""
    archiveURL = ""

    wikiFile = None

    def __init__(self, config, episode, episodeDate):
        self.episodeNumber = episode
        if(episodeDate):
            self.episodeDate = episodeDate
        
        # read config entries
        try:
            self.filePath = config.get('ListCommon', 'filePath')
            self.archiveURL = config.get('ListCommon', 'archiveURL')
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

        fileDate = '{dt:%Y}{dt:%m}{dt:%d}'.format(dt=self.episodeDate)
        self.archiveURL = f"{self.archiveURL}{fileDate}.mp3"

        headerText = "Subject: " + self.getEpisodeTitle(self.episodeNumber) + "\n"
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

    def logTrack(self, track, startTime):
        if( track.ignore is not True ):
            trackText = (f"<tr>\n"
                        f"<td>{track.title}</td>"
                        f"<td>{track.artist}</td>"
                        f"<td>{track.album}</td>"
                        f"</tr>")


            self.logToFile(self.blogFile, trackText)

        return

    def close(self):
        print("Closing Blog File...")

        self.logToFile(self.blogFile, "\n</tbody>")
        self.logToFile(self.blogFile, "</table>")

        self.blogFile.close()
        
        return
