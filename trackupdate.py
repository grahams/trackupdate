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
import logging

from appscript import *

pluginList = { }

class TrackUpdate(object):
    ignoreAlbum = ""
    trackArtist = ""
    trackName  = ""
    trackAlbum = ""
    trackTime = ""
    episodeNumber = "XX"
    pollTime = 10
    startTime = -1

    def usage(self):
        print( "Usage: trackupdate.py [arguments]" )
        print( """
This is a simple script which polls iTunes every (default) 10 seconds and writes information about the current track to Nicecast's "NowPlaying.txt" file.

Arguments:
    -e  --episode     the episode number (optional, used by some plugins)
    -t  --polltime    the time to wait between polling iTunes
    -h  --help        show this help page
    -v  --verbose     you are lonely and want trackupdate to talk more

Example:
    ./trackupdate.py -e 42
    """)

    def __init__(self,argv):
        
        config = None
        logging.basicConfig(level=logging.WARNING)

        # process config file
        try:
            config = ConfigParser.ConfigParser()
            config.read(os.path.expanduser('~/.trackupdaterc'))
        except ConfigParser.MissingSectionHeaderError:
            logging.warning("Warning: Invalid config file, no [trackupdate] section.")
            raise

        try:
            self.ignoreAlbum = config.get('trackupdate', 'ignoreAlbum')
            self.pollTime = int(config.get('trackupdate', 'pollTime'))
        except ConfigParser.NoSectionError:
            pass

        # process command-line arguments
        if(len(argv) > 0):
            try:
                opts, args = getopt.getopt(sys.argv[1:], "h:e:t:v", ["help",
                                                                   "episode=", "polltime=", "verbose"])
            except getopt.GetoptError, err:
                # print help information and exit:
                logging.error(str(err)) # will print something like "option -a not recognized"
                self.usage()
                sys.exit(2)

            for o, a in opts:
                if o in ("-e", "--episode"):
                    self.episodeNumber = a
                elif o in ("-t", "--polltime"):
                    a = int(a)
                    if a >= 0: a = 1
                    self.pollTime = a
                elif o in ("-v", "--verbose"):
                    # remove any logging handlers created by logging before
                    # BasicConfig() is called
                    root = logging.getLogger()
                    if root.handlers:
                        for handler in root.handlers:
                            root.removeHandler(handler)

                    logging.basicConfig(level=logging.DEBUG)
                    logging.debug("Starting up. Press Ctrl-C to stop.")
                elif o in ("-h", "--help"):
                    self.usage()
                    sys.exit()
                else:
                    assert False, "unhandled option"

        self.loadPlugins(config, self.episodeNumber)
        logging.debug( "   Episode #: %s" % str(self.episodeNumber) )
        logging.debug( "   Time between polling: %i\n" % self.pollTime )


        try:
            iTunes = app('iTunes')
            theNC = app('Nicecast')
            theNC.start_archiving() #Force nicecast to start archiving things
            #maybe there is an applescript way to ask nicecast for the path to the archive vs defining it in the rc?
            #looks like nicecast stores its pref file at ~/Library/Preferences/com.rogueamoeba.Nicecast.plist
            #since the user can't force nicecast to store its pref file in a custom location, one could pull the archive dir from the plist
            #http://docs.python.org/library/plistlib.html
            while(1):
                if ((iTunes.player_state() == k.playing) and (theNC.archiving()) and (theNC.broadcasting()) and (self.startTime==-1) and (not iTunes.current_track.album.get()==self.ignoreAlbum)): 
                    self.startTime=time.time()		
                if (iTunes.player_state() == k.playing): self.processCurrentTrack(iTunes.current_track)

                time.sleep(self.pollTime)

        except KeyboardInterrupt,SystemExit:
            logging.debug("\n***Exiting...")
            for plugin in pluginList:
                try:
                    pluginList[plugin].close()
                except:
                    logging.error(plugin + ": Error trying to close target")

    def processCurrentTrack(self, currentTrack):
        iArtist = currentTrack.artist.get()
        iName = currentTrack.name.get()
        iAlbum = currentTrack.album.get()
        iTime = currentTrack.time.get()
        if(not currentTrack.artworks.get()==[]):
            theFormatAE = currentTrack.artworks[1].format.get()
            #apparently there is no 'png' format, so set it to 'png' and overwrite as necessary
            theFormat='png'
            if(theFormatAE==k.JPEG_picture): theFormat='jpg'
            if(theFormatAE==k.GIF_picture): theFormat='gif'
            #remove the first 221 bytes to strip off the stupid pict header
            iArt = [currentTrack.artworks[1].data_.get().data[222:], theFormat]
        else:
            iArt = []
        
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
                logging.info("Album title on blacklist: " + iArtist + " - " + iName + " - " + iAlbum)
                return
				
            for plugin in pluginList:
                try:
                    pluginList[plugin].logTrack(iName, iArtist, iAlbum, iTime, iArt, self.startTime)
                except:
                    logging.error(plugin + ": Error trying to update track")


    def loadPlugins(self, config, episode):
        logging.debug("Loading plugins...")
        scriptPath = "."
        #***this doesn't work for me. STH 11.05.15***
        #***using os.path.split(__file__)[0] returns "" on my machine, and no plugins are loaded. It can't find the plugin folder at all
        #scriptPath = os.path.split(__file__)[0]
        sys.path.append(scriptPath)
        sys.path.append(scriptPath + "/plugins/")
        pluginNames = glob.glob(scriptPath + "/plugins/*.py")
        
        for x in pluginNames:
            className = x.replace(".py","").replace(scriptPath + "/plugins/","")
            enabled = 'False'

            #if the .rc doesn't define whether it is enabled, defaults to False
            try:
                enabled = config.get(className, 'enabled')
            except ConfigParser.NoSectionError:
                enabled = 'False'
            except ConfigParser.NoOptionError:
                enabled = 'False'

            if(enabled=='False'):
                logging.debug("   Skipping plugin '%s'." % className)
            else:
                logging.debug("   Loading plugin '%s'...." % className)

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