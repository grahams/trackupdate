#!/usr/bin/python

# Copyright (c) 2009 Sean M. Graham <www.sean-graham.com>
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
import time

from appscript import *

iTunes = app('iTunes')

tArtist = ""
tName  = ""
tAlbum = ""
tTime = ""

while(1):
    if(iTunes.player_state() == k.playing):
        itArtist = iTunes.current_track.artist.get().encode("utf-8")
        itName = iTunes.current_track.name.get().encode("utf-8")
        itAlbum = iTunes.current_track.album.get().encode("utf-8")
        itTime = iTunes.current_track.time.get().encode("utf-8")

        if( (itArtist != tArtist) or (itName != tName) ):
            tArtist = itArtist
            tName  = itName
            tAlbum = itAlbum
            tTime = itTime

            fh = open(os.path.expanduser('~/Library/Application Support/Nicecast/NowPlaying.txt'), 'w')
            fh.write("Title: " + tName + '\n')
            fh.write("Artist: " + tArtist  + '\n')
            fh.write("Album: " + tAlbum  + '\n')
            fh.write("Time: " + tTime  + '\n')
            fh.close()
            
            print tArtist + " - " + tName 

    time.sleep(10.0)
