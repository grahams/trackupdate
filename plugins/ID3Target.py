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
import glob

import id3 # http://github.com/myers/pyid3

from mx.DateTime import * # http://pypi.python.org/pypi/egenix-mx-base/3.1.2

class ID3Target(Target):
    pluginName = "ID3 Tag Writer"
    daySuffix = "th"

    filePath = ""
    albumName = ""
    artistName = ""
    
    def __init__(self, config, episode):
        self.today = now()

        # read config entries
        try:
            self.filePath = config.get('id3', 'filePath')
            self.albumName = config.get('id3', 'albumName')
            self.artistName = config.get('id3', 'artistName')
        except ConfigParser.NoSectionError:
            print("ID3Target: No [id3] section in config")
            return
        except ConfigParser.NoOptionError:
            print("ID3Target: Missing values in config")
            return

        # if I gave a shit about non-unix platforms I might
        # try to use the proper path sep here. exercise left 
        # for the reader.
        if(self.filePath.endswith("/") != True):
            self.filePath += "/"

        # handle stupid date suffix.  i'm sure there is a better way to do
        # this
        if( (self.today.day == 1) | (self.today.day == 21) | 
            (self.today.day == 31) ):
            self.daySuffix = "st"

        if( (self.today.day == 2) | (self.today.day == 22) ):
            self.daySuffix = "nd"

        if( (self.today.day == 3) | (self.today.day == 23) ):
            self.daySuffix = "rd"

    def close(self):
        titleDate = self.today.strftime("%B %e" + self.daySuffix + ", %Y")
        fileDate = self.today.strftime("%Y%m%d")
        year = self.today.strftime("%Y")

        files = glob.glob(self.filePath + 
                          "Nicecast Archived Audio " + 
                          fileDate + "*.mp3")

        if(len(files) < 1):
            return

        # assumes that there is only one archive file for the day
        id3v2 = id3.ID3v2( files[0] )

        f = id3v2.new_frame('TIT2')
        f.value = titleDate

        f = id3v2.new_frame('TPE1')
        f.value = self.artistName
        
        f = id3v2.new_frame('TALB')
        f.value = self.albumName

        f = id3v2.new_frame('TYER')
        f.value = year

        id3v2.save()

    def logTrack(self, title, artist, album, time):
        return
