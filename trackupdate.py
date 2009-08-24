#!/usr/bin/python

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
