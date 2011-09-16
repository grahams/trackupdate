#!/usr/bin/env python

# Copyright (c) 2009-2011 Sean M. Graham <www.sean-graham.com>
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

import appscript
from appscript import *

pluginList = { }

class TrackUpdate(object):
    introAlbum = ""
    trackArtist = ""
    trackName  = ""
    trackAlbum = ""
    trackTime = ""
    episodeNumber = "XX"
    pollTime = 10
    startTime = -1
    useStopValues = False
    stopTitle = ""
    stopArtist = ""
    stopAlbum = ""

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
    ./trackupdate.py -e 42 -t 5 -v
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
            self.introAlbum = config.get('trackupdate', 'introAlbum')
            self.pollTime = int(config.get('trackupdate', 'pollTime'))
            self.useStopValues = config.get('trackupdate', 'useStopValues')
            self.stopTitle = config.get('trackupdate', 'stopTitle')
            self.stopArtist = config.get('trackupdate', 'stopArtist')
            self.stopAlbum = config.get('trackupdate', 'stopAlbum')
        except ConfigParser.NoSectionError:
            pass

        # process command-line arguments
        if(len(argv) > 0):
            try:
                opts, args = getopt.getopt(sys.argv[1:], "h:e:t:v", ["help",
                                           "episode=", "polltime=", "verbose"])
            except getopt.GetoptError, err:
                # print help information and exit:
                logging.error(str(err)) # will print something like 
                                        # "option -a not recognized"
                self.usage()
                sys.exit(2)

            for o, a in opts:
                if o in ("-e", "--episode"):
                    self.episodeNumber = a
                elif o in ("-t", "--polltime"):
                    a = int(a)
                    if(a <= 0):
                        a = 1

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
        logging.debug("Episode #: %s" % str(self.episodeNumber))
        logging.debug("Time between polling: %i" % self.pollTime)

        try:
            it = app('iTunes')
            nc = app('Nicecast')

            if(self.introAlbum != ""):
                logging.debug("Disabling Archiving until intro over")
                nc.stop_archiving() 

                while(1):
                    if(self.startTime==-1):
                        if((it.player_state() == k.paused) or
                           (it.player_state() == k.stopped) or
                           ((it.player_state() == k.playing) and
                            (it.current_track.album.get() == 
                                    self.introAlbum))
                          ):
                            time.sleep(self.pollTime)
                        else:
                            logging.debug("Enabling Archiving")
                            nc.start_archiving() 
                            break
                    else:
                        logging.debug("Enabling Archiving")
                        nc.start_archiving() 
                        break
            else:
                logging.debug("Enabling Archiving")
                nc.start_archiving() 

            while(1):
                if((it.player_state() == k.playing) and 
                   (nc.archiving()) and 
                   (nc.broadcasting()) and 
                   (self.startTime==-1)):
                    # don't start the timeline until the intro is over
                    self.startTime=time.time()		

                if(it.player_state() == k.playing): 
                    self.processCurrentTrack(it.current_track)
                elif(self.useStopValues == 'True'):
                    self.updateTrack(self.stopTitle, 
                                     self.stopArtist,
                                     self.stopAlbum, 
                                     "9:99", 
                                     [], 
                                     self.startTime)
                        
                    

                time.sleep(self.pollTime)

        except (appscript.reference.CommandError):
            logging.error("Appscript error caught: winding down")
            self.cleanUp(nc)

        except (KeyboardInterrupt,SystemExit):
            self.cleanUp(nc)

    def cleanUp(self, nc):
        logging.debug("Exiting...")
        logging.debug("Disabling Archiving")

        try:
            nc.stop_archiving() 
        except (appscript.reference.CommandError):
            logging.error("Nicecast no longer running, unable to stop archiving")

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

        try:
            if(not currentTrack.artworks.get()==[]):
                theFormatAE = currentTrack.artworks[1].format.get()
                # apparently there is no 'png' format, so set it to 'png' and
                # overwrite as necessary added more formats to try and catch any
                # weird ones
                theFormat='png'

                if(theFormatAE == k.JPEG_picture): 
                    theFormat='jpg'
                elif(theFormatAE == k.GIF_picture): 
                    theFormat='gif'
                elif(theFormatAE == k.PICT_picture): 
                    theFormat='pict'
                elif(theFormatAE == k.TIFF_picture): 
                    theFormat='tiff'
                elif(theFormatAE == k.EPS_picture): 
                    theFormat='eps'
                elif(theFormatAE == k.BMP_picture): 
                    theFormat='bmp'

                try:
                    # there was a bug recently I can't track down. Just catch
                    # the problem and carry on remove the first 221 bytes to
                    # strip off the stupid pict header
                    iArt = [currentTrack.artworks[1].data_.get().data[222:], theFormat]
                except:
                    logging.error("Error trying to get art for track: " + iName)
                    logging.error("Detected format was: " + theFormat)
                    iArt = []
            else:
                iArt = []
        except:
            # getting art has caused trouble
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

        self.updateTrack(iName, iArtist, iAlbum, 
                         iTime, iArt, self.startTime)

    def updateTrack(self, name, artist, album, time, art, startTime):
        # make sure the track has actually changed
        if( (artist != self.trackArtist) or (name != self.trackName) ):
            self.trackArtist = artist
            self.trackName  = name
            self.trackAlbum = album
            self.trackTime = time

            for plugin in pluginList:
                try:
                    pluginList[plugin].logTrack(name, artist, album,    
                                                time, art, startTime)
                except:
                    logging.error(plugin + ": Error trying to update track")
        

    def loadPlugins(self, config, episode):
        logging.debug("Loading plugins...")

        scriptPath = os.path.split(os.path.abspath(__file__))[0]
        
        sys.path.append(scriptPath)
        sys.path.append(scriptPath + "/plugins/")
        pluginNames = glob.glob(scriptPath + "/plugins/*.py")
        for x in pluginNames:
            className = x.replace(".py","").replace(scriptPath + "/plugins/","")
            enabled = 'False'

            # if the .rc doesn't define whether it is enabled, defaults to False
            try:
                enabled = config.get(className, 'enabled')
            except ConfigParser.NoSectionError:
                enabled = 'False'
            except ConfigParser.NoOptionError:
                enabled = 'False'

            if(enabled=='False'):
                logging.debug("Skipping plugin '%s'." % className)
            else:
                logging.debug("Loading plugin '%s'...." % className)

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
