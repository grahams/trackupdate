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

import os
from datetime import date

class WikiTarget(Target):
    wfh = None
    pluginName = "Wiki Text Generator"
    createWikiText = False
    wikiFilePath = ""
    wikiArchiveURL = ""
    episodeNumber = "XX"

    def __init__(self, config, episode):
        self.episodeNumber = episode

        try:
            self.wikiFilePath = config.get('wiki', 'wikiTextDirectory')
            self.wikiArchiveURL = config.get('wiki', 'wikiArchiveURL')
            self.ignoreAlbum = config.get('trackupdate', 'ignoreAlbum')
        except ConfigParser.NoSectionError:
            print("NoSectionError")
            return
        except ConfigParser.NoOptionError:
            print("NoOptionError")
            return

        if(self.wikiFilePath != ""):
            self.createWikiText = True
            self.initWikiFile()

    def close(self):
        if( self.createWikiText == True ):
            self.wfh.write("|}\n")
            self.wfh.close()
        
    def logTrack(self, title, artist, album, time):
        if( self.createWikiText == True ):
            self.wfh.write("|" + title + '\n')
            self.wfh.write("|" + artist + '\n')
            self.wfh.write("|" + album + '\n')
            self.wfh.write("|-\n")

    def initWikiFile(self):
        dateString = date.today().strftime("%Y%m%d")

        filename = os.path.expanduser(self.wikiFilePath + dateString + 
                                      "-wikitext.txt")

        # if the file already exists, delete it
        if(os.access(filename, os.F_OK)):
            os.unlink(filename)

        self.wfh = open(filename, 'a')

        self.wfh.write("=== ")

        if(self.wikiArchiveURL != ""):
            self.wfh.write("[" + date.today().strftime(self.wikiArchiveURL) + " ")

        self.wfh.write("Show #" + self.episodeNumber + " - ")

        # compute the suffix
        day = date.today().day
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = ["st", "nd", "rd"][day % 10 - 1]

        self.wfh.write(date.today().strftime("%A, %B %d"))
        self.wfh.write(suffix)
        self.wfh.write(date.today().strftime(", %Y"))

        if(self.wikiArchiveURL != ""):
            self.wfh.write("]")

        self.wfh.write(" ===\n")

        self.wfh.write("{| border=1 cellspacing=0 cellpadding=5\n")
        self.wfh.write("|'''Song'''\n")
        self.wfh.write("|'''Artist'''\n")
        self.wfh.write("|'''Album'''\n")
        self.wfh.write("|-\n")

