#!/usr/bin/python

# Copyright (c) 2009-2010 Sean M. Graham <www.sean-graham.com>
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
import glob

from appscript import *

pluginList = { }

class TrackUpdate:
    ignoreAlbum = ""
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
    -e  --episode   the episode number (optional, used by some plugins)
    -h  --help      show this help page

Example:
    ./trackupdate.py -e 42
    """)

    def __init__(self,argv):
        config = None

        # process config file
        try:
            config = ConfigParser.ConfigParser()
            config.read(os.path.expanduser('~/.trackupdaterc'))
        except ConfigParser.MissingSectionHeaderError:
            print "Warning: Invalid config file, no [trackupdate] section."

        try:
            self.ignoreAlbum = config.get('trackupdate', 'ignoreAlbum')
        except ConfigParser.NoSectionError:
            pass

        # process command-line arguments
        if(len(argv) > 0):
            try:
                opts, args = getopt.getopt(sys.argv[1:], "h:e:", ["help",
                                                                   "episode="])
            except getopt.GetoptError, err:
                # print help information and exit:
                print str(err) # will print something like "option -a not recognized"
                self.usage()
                sys.exit(2)

            for o, a in opts:
                if o in ("-e", "--episode"):
                    self.episodeNumber = a
                elif o in ("-h", "--help"):
                    self.usage()
                    sys.exit()
                else:
                    assert False, "unhandled option"

        self.loadPlugins(config, self.episodeNumber)

        try:
            iTunes = app('iTunes')

            while(1):
                if(iTunes.player_state() == k.playing):
                    self.processCurrentTrack(iTunes.current_track)

                time.sleep(10.0)

        except KeyboardInterrupt,SystemExit:
            for plugin in pluginList:
                pluginList[plugin].close()


    def processCurrentTrack(self, currentTrack):
        iArtist = currentTrack.artist.get()
        iName = currentTrack.name.get()
        iAlbum = currentTrack.album.get()
        iTime = currentTrack.time.get()

        # check for missing values
        if( iArtist != k.missing_value ):
            iArtist = iArtist.encode("utf-8")
        else:
            iArtist = ""

        if( iName != k.missing_value ):
            iName = iName.encode("utf-8")
        else:
            iName = ""

        if( iAlbum != k.missing_value ):
            iAlbum = iAlbum.encode("utf-8")
        else:
            iAlbum = ""

        if( iTime != k.missing_value ):
            iTime = iTime.encode("utf-8")
        else:
            iTime = ""

        # make sure the track has actually changed
        if( (iArtist != self.trackArtist) or (iName != self.trackName) ):
            self.trackArtist = iArtist
            self.trackName  = iName
            self.trackAlbum = iAlbum
            self.trackTime = iTime

            # if the album name matches the blacklist name don't do anything
            if( self.trackAlbum == self.ignoreAlbum ):
                return

            for plugin in pluginList:
                try:
                    pluginList[plugin].logTrack(iName, iArtist, iAlbum, iTime)
                except:
                    print(plugin + ": Error Trying to update track")


    def loadPlugins(self, config, episode):
        scriptPath = "."
        sys.path.append(scriptPath)
        sys.path.append(scriptPath + "/plugins/")
        pluginNames = glob.glob(scriptPath + "/plugins/*.py")

        for x in pluginNames:
            pathName = x.replace(".py","")
            className = x.replace(".py","").replace(scriptPath + "/plugins/","")

            # import the module
            mod = __import__(className, globals(), locals(), [''])

            # find the symbol for the class
            cls  = getattr(mod,className)

            # initialize the plugin
            o = cls(config,episode)

            # add the plugin to the list
            pluginList[ o.pluginName ] = o

if __name__ == "__main__":
    trackUpdate = TrackUpdate(sys.argv[1:])
