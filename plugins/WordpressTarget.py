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
import sys

import markup        # http://markup.sourceforge.net/
import wordpresslib  # http://pypi.python.org/pypi/WordPress%20Python%20Library

from mx.DateTime import * # http://pypi.python.org/pypi/egenix-mx-base/3.1.2

class WordpressTarget(Target):
    pluginName = "Wordpress Track Updater"
    today = now()
    daySuffix = "th"

    def __init__(self, config, episode):
        # pull config values
        self.username = config.get('WordpressTarget', 'username')
        self.password = config.get('WordpressTarget', 'password')
        self.xmlrpc = config.get('WordpressTarget', 'xmlrpc')
        self.blogId = config.get('WordpressTarget', 'blogId')
        
        # handle stupid date suffix.  i'm sure there is a better way to do
        # this
        if( (self.today.day == 1) | (self.today.day == 21) | 
            (self.today.day == 31) ):
            self.daySuffix = "st"

        if( (self.today.day == 2) | (self.today.day == 22) ):
            self.daySuffix = "nd"

        if( (self.today.day == 3) | (self.today.day == 23) ):
            self.daySuffix = "rd"

        # set up page and table headers
        self.page = markup.page(mode="loose_html")

        self.page.table.open(border=1, cellspacing=0, cellpadding=5)

        self.page.thead.open()
        self.page.tr.open()

        self.page.td.open()
        self.page.strong.open()
        self.page.add("Song")
        self.page.strong.close()
        self.page.td.close()

        self.page.td.open()
        self.page.strong.open()
        self.page.add("Artist")
        self.page.strong.close()
        self.page.td.close()

        self.page.td.open()
        self.page.strong.open()
        self.page.add("Album")
        self.page.strong.close()
        self.page.td.close()

        self.page.tr.close()
        self.page.thead.close()

        self.page.tbody.open()

    def close(self):
        print("Posting to Wordpress")

        self.page.tbody.close()
        self.page.table.close()

        date = self.today.strftime("%B %e" + self.daySuffix + ", %Y")

        wp = wordpresslib.WordPressClient(self.xmlrpc, 
                                          self.username, 
                                          self.password)

        wp.selectBlog(self.blogId)

        post = wordpresslib.WordPressPost()

        post.title = date
        post.description = str(self.page)

        idPost = wp.newPost(post, True)

    def logTrack(self, title, artist, album, time, startTime):
        self.page.tr.open()

        self.page.td.open()
        self.page.add(title)
        self.page.td.close()

        self.page.td.open()
        self.page.add(artist)
        self.page.td.close()

        self.page.td.open()
        self.page.add(album)
        self.page.td.close()

        self.page.tr.close()
