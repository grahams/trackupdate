#!/opt/local/bin/python

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
import ConfigParser

from datetime import date
from appscript import *

nowPlayingFilePath = os.path.expanduser('~/Library/Application Support/Nicecast/NowPlaying.txt')

class TrackUpdate:
    wfh = None
    wikiFilePath = ""
    wikiArchiveURL = ""
    ignoreAlbum = ""
    createWikiText = False
    trackArtist = ""
    trackName  = ""
    trackAlbum = ""
    trackTime = ""
    episodeNumber = "XX"

    def usage(self):
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

    def __init__(self,argv):
        # process config file
        try:
            config = ConfigParser.ConfigParser()
            config.read(os.path.expanduser('~/.trackupdaterc'))
        except ConfigParser.MissingSectionHeaderError:
            print "Warning: Invalid config file, no [trackupdate] section."

        try:
            self.wikiFilePath = config.get('wiki', 'wikiTextDirectory')
            self.wikiArchiveURL = config.get('wiki', 'wikiArchiveURL')
            self.ignoreAlbum = config.get('trackupdate', 'ignoreAlbum')
        except ConfigParser.NoSectionError:
            pass
        except ConfigParser.NoOptionError:
            pass

        if(self.wikiFilePath != ""):
            self.createWikiText = True

        # process command-line arguments
        if(len(argv) > 0):
            try:
                opts, args = getopt.getopt(sys.argv[1:], "hw:e:", ["help",
                                                                   "wiki=",
                                                                   "episode="])
            except getopt.GetoptError, err:
                # print help information and exit:
                print str(err) # will print something like "option -a not recognized"
                self.usage()
                sys.exit(2)

            for o, a in opts:
                if o in ("-w", "--wiki"):
                    self.createWikiText = True
                    self.wikiFilePath = a
                elif o in ("-e", "--episode"):
                    self.episodeNumber = a
                elif o in ("-h", "--help"):
                    self.usage()
                    sys.exit()
                else:
                    assert False, "unhandled option"

        if(self.wikiFilePath.endswith('/') != True):
            self.wikiFilePath += "/"

        try:
            iTunes = app('iTunes')

            # prepare wiki text file (if the user requested it)
            if( self.createWikiText == True ):
                self.initWikiFile()

            while(1):
                if(iTunes.player_state() == k.playing):
                    self.processCurrentTrack(iTunes.current_track)

                time.sleep(10.0)

        except KeyboardInterrupt,SystemExit:
            if( (self.createWikiText == True) and (self.wfh != None) ):
                self.wfh.write("|}\n")
                self.wfh.close()
            os.remove(nowPlayingFilePath)


    def processCurrentTrack(self, currentTrack):
        iArtist = currentTrack.artist.get().encode("utf-8")
        iName = currentTrack.name.get().encode("utf-8")
        iAlbum = currentTrack.album.get().encode("utf-8")
        iTime = currentTrack.time.get().encode("utf-8")

        # make sure the track has actually changed
        if( (iArtist != self.trackArtist) or (iName != self.trackName) ):
            self.trackArtist = iArtist
            self.trackName  = iName
            self.trackAlbum = iAlbum
            self.trackTime = iTime

            # if the album name matches the blacklist name don't do anything
            if( self.trackAlbum == self.ignoreAlbum ):
                return

            fh = open(nowPlayingFilePath, 'w')
            fh.write("Title: " + self.trackName + '\n')
            fh.write("Artist: " + self.trackArtist  + '\n')
            fh.write("Album: " + self.trackAlbum  + '\n')
            fh.write("Time: " + self.trackTime  + '\n')
            fh.close()

            if( self.createWikiText == True ):
                self.wfh.write("|" + self.trackName + '\n')
                self.wfh.write("|" + self.trackArtist + '\n')
                self.wfh.write("|" + self.trackAlbum + '\n')
                self.wfh.write("|-\n")
            
            print self.trackArtist + " - " + self.trackName 

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

if __name__ == "__main__":
    trackUpdate = TrackUpdate(sys.argv[1:])
