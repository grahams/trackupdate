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
from datetime import date

# http://code.google.com/p/python-wikitools/
from wikitools import wiki
from wikitools import api
from wikitools import Page
from wikitools import pagelist

class WikiTarget(Target):
    pluginName = "Wiki Text Generator"
    createWikiText = False
    episodeNumber = "XX"
    text = ""

    # config values
    wikiApiURL = ""
    wikiUsername = ""
    wikiPassword = ""
    wikiPageName = ""
    wikiArchiveURL = ""

    def __init__(self, config, episode):
        self.episodeNumber = episode

        try:
            self.wikiApiURL = config.get('WikiTarget', 'wikiApiURL')
            self.wikiUsername = config.get('WikiTarget', 'wikiUsername')
            self.wikiPassword = config.get('WikiTarget', 'wikiPassword')
            self.wikiPageName = config.get('WikiTarget', 'wikiPageName')
            self.wikiArchiveURL = config.get('WikiTarget', 'wikiArchiveURL')
        except ConfigParser.NoSectionError:
            print("WikiTarget: No [WikiTarget] section in config")
            return
        except ConfigParser.NoOptionError:
            print("NoOptionError")
            return

        self.createWikiText = True
        self.initWikiFile()

    def close(self):
        if( self.createWikiText == True ):
            self.text += "|}"

            print("Posting to Wiki...")

            site = wiki.Wiki(self.wikiApiURL)
            site.login(self.wikiUsername, self.wikiPassword)
            page = Page(site, title=self.wikiPageName)
            page.edit(appendtext=self.text)

        
    def logTrack(self, title, artist, album, time, startTime):
        if( self.createWikiText == True ):
            self.text += "|" + title + '\n'
            self.text += "|" + artist + '\n'
            self.text += "|" + album + '\n'
            self.text += "|-\n"

    def initWikiFile(self):
        self.text += "\n\n=== "

        if(self.wikiArchiveURL != ""):
            self.text += "[" + date.today().strftime(self.wikiArchiveURL) + " "

        self.text += "Show #" + self.episodeNumber + " - "

        # compute the suffix
        day = date.today().day
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = ["st", "nd", "rd"][day % 10 - 1]

        self.text += date.today().strftime("%A, %B %d")
        self.text += suffix
        self.text += date.today().strftime(", %Y")

        if(self.wikiArchiveURL != ""):
            self.text += "]"

        self.text += " ===\n"

        self.text += "{| border=1 cellspacing=0 cellpadding=5\n"
        self.text += "|'''Song'''\n"
        self.text += "|'''Artist'''\n"
        self.text += "|'''Album'''\n"
        self.text += "|-\n"

