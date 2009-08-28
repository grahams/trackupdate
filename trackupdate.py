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
import sys
import getopt

from datetime import date
from appscript import *

def usage():
    print( "Usage: trackupdate.py [arguments]" )
    print( """
This is a simple script which polls iTunes every 10 seconds and writes information about the current track to Nicecast's "NowPlaying.txt" file.

Arguments:
    -w  --wiki      directory to place wiki-formatted table of songs (optional) 
    -e  --episode   the episode number (optional, only used in wiki text)
    -h  --help      show this help page

Example:
    ./trackupdate.py --wiki ~/aatemp/ 
""")

wfh = None
wikiFilePath = ""
createWikiText = False
trackArtist = ""
trackName  = ""
trackAlbum = ""
trackTime = ""
episodeNumber = "XX"

def main(argv):
    # process command-line arguments
    if(len(argv) > 0):
        try:
            opts, args = getopt.getopt(sys.argv[1:], "hw:e:", ["help",
                                                               "wiki=",
                                                               "episode="])
        except getopt.GetoptError, err:
            # print help information and exit:
            print str(err) # will print something like "option -a not recognized"
            usage()
            sys.exit(2)

        for o, a in opts:
            if o in ("-w", "--wiki"):
                global createWikiText
                global wikiFilePath 

                createWikiText = True
                wikiFilePath = a
                if(wikiFilePath.endswith('/') != True):
                    wikiFilePath += "/"
            elif o in ("-e", "--episode"):
                global episodeNumber

                episodeNumber = a
            elif o in ("-h", "--help"):
                usage()
                sys.exit()
            else:
                assert False, "unhandled option"

    try:
        iTunes = app('iTunes')

        # prepare wiki text file (if the user requested it)
        if( createWikiText == True ):
            initWikiFile()

        while(1):
            if(iTunes.player_state() == k.playing):
                processCurrentTrack(iTunes.current_track)

            time.sleep(10.0)

    except KeyboardInterrupt,SystemExit:
        global wfh
        if( (createWikiText == True) and (wfh != None) ):
            wfh.write("|}\n")
            wfh.close()

def processCurrentTrack(currentTrack):
    global trackArtist
    global trackName
    global trackAlbum
    global trackTime

    iArtist = currentTrack.artist.get().encode("utf-8")
    iName = currentTrack.name.get().encode("utf-8")
    iAlbum = currentTrack.album.get().encode("utf-8")
    iTime = currentTrack.time.get().encode("utf-8")

    # make sure the track has actually changed
    if( (iArtist != trackArtist) or (iName != trackName) ):
        trackArtist = iArtist
        trackName  = iName
        trackAlbum = iAlbum
        trackTime = iTime

        fh = open(os.path.expanduser(
            '~/Library/Application Support/Nicecast/NowPlaying.txt'), 'w')
        fh.write("Title: " + trackName + '\n')
        fh.write("Artist: " + trackArtist  + '\n')
        fh.write("Album: " + trackAlbum  + '\n')
        fh.write("Time: " + trackTime  + '\n')
        fh.close()

        global createWikiText
        if( createWikiText == True ):
            global wfh
            wfh.write("|" + trackName + '\n')
            wfh.write("|" + trackArtist + '\n')
            wfh.write("|" + trackAlbum + '\n')
            wfh.write("|-\n")
        
        print trackArtist + " - " + trackName 

def initWikiFile():
    global wikiFilePath 

    dateString = date.today().strftime("%Y%m%d")
    filename = os.path.expanduser(wikiFilePath + dateString + 
                                  "-wikitext.txt")

    # if the file already exists, delete it
    if(os.access(filename, os.F_OK)):
        os.unlink(filename)

    # XXX: The filename/URL shouldn't be hardcoded...
    global wfh
    global episodeNumber
    wfh = open(filename, 'a')
    wfh.write("=== [http://s3.amazonaws.com/08BJY5WG66W8YBZ9QHG2.media/grahamscast/")
    wfh.write(dateString)
    wfh.write("%20-%20grahams'%20completely%20normal%20radio%20programme.mp3 ")
    wfh.write("Show #" + episodeNumber + " - ")

    # compute the suffix
    day = date.today().day
    if 4 <= day <= 20 or 24 <= day <= 30:
        suffix = "th"
    else:
        suffix = ["st", "nd", "rd"][day % 10 - 1]

    wfh.write(date.today().strftime("%A, %B %d"))
    wfh.write(suffix)
    wfh.write(date.today().strftime(", %Y] ===\n"))
    wfh.write("""{| border=1 cellspacing=0 cellpadding=5
|'''Song'''
|'''Artist'''
|'''Album'''
|-
""")

if __name__ == "__main__":
    main(sys.argv[1:])
