#!/usr/bin/env python2.7

# Copyright (c) 2009-2014 Sean M. Graham <www.sean-graham.com>
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
import subprocess
import json

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
        #STH 2017-0524 the following wouldn't actually catch whether .trackupdaterc
        #is missing, and wouldn't see whether it had a [trackupdate] section
        # try:
        #     config = ConfigParser.ConfigParser()
        #     config.read(os.path.expanduser('~/.trackupdaterc'))
        # except ConfigParser.MissingSectionHeaderError:
        #     logging.warning("Warning: Invalid config file, no [trackupdate] section.")
        #     raise
        if not os.path.isfile(os.path.expanduser('~/.trackupdaterc')):
            logging.warning("Warning: no config .trackupdaterc file.")

        config = ConfigParser.ConfigParser()
        config.read(os.path.expanduser('~/.trackupdaterc'))

        try:
            self.introAlbum = config.get('trackupdate', 'introAlbum')
            self.pollTime = int(config.get('trackupdate', 'pollTime'))
            self.useStopValues = config.get('trackupdate', 'useStopValues')
            self.stopTitle = config.get('trackupdate', 'stopTitle')
            self.stopArtist = config.get('trackupdate', 'stopArtist')
            self.stopAlbum = config.get('trackupdate', 'stopAlbum')
        except ConfigParser.NoSectionError:
            logging.warning("Warning: Invalid config file, no [trackupdate] section.")
            pass
        except ConfigParser.NoOptionError:
            print("[trackupdate]: Missing values in config")
            return


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
            if(self.introAlbum != ""):
            #     logging.debug("Disabling Archiving until intro over")
            #     nc.stop_archiving() 

                while(1):
                    if(self.startTime==-1):
                        track = json.loads(subprocess.check_output(["osascript",
                                             "Automation/GetCurrentTrackJSON.scpt"]))
                        album = None

                        if('album' in track.keys()):
                            album = track['album']
                        

                        if((len(track) == 0) or (album == self.introAlbum)):
                            time.sleep(self.pollTime)
                        else:
                            # logging.debug("Enabling Archiving")
                            # nc.start_archiving() 
                            break
                    else:
                        # logging.debug("Enabling Archiving")
                        # nc.start_archiving() 
                        break
            # else:
            #     logging.debug("Enabling Archiving")
            #     nc.start_archiving() 

            while(1):
                # if((it.player_state() == k.playing) and 
                #    (nc.archiving()) and 
                #    (nc.broadcasting()) and 
                #    (self.startTime==-1)):
                #     # don't start the timeline until the intro is over
                #     self.startTime=time.time()		

                track = json.loads(subprocess.check_output(["osascript",
                                     "Automation/GetCurrentTrackJSON.scpt"]))

                if(len(track) > 0):
                    self.processCurrentTrack(track)
                elif(self.useStopValues == 'True'):
                    self.updateTrack(self.stopTitle, 
                                     self.stopArtist,
                                     self.stopAlbum, 
                                     "9:99", 
                                     self.startTime)
                        
                    

                time.sleep(self.pollTime)
        except (KeyboardInterrupt,SystemExit):
            self.cleanUp()

    def cleanUp(self):
        logging.debug("Exiting...")
        # logging.debug("Disabling Archiving")

        # try:
        #     nc.stop_archiving() 
        # except (appscript.reference.CommandError):
        #     logging.error("Nicecast no longer running, unable to stop archiving")

        for plugin in pluginList:
            try:
                pluginList[plugin].close()
            except:
                logging.error(plugin + ": Error trying to close target")
    

    def processCurrentTrack(self, t):
        iArtist = ""
        iName = ""
        iAlbum = ""
        iTime = ""

        if('artist' in t.keys()):
            iArtist = t['artist']
        if('name' in t.keys()):
            iName = t['name']
        if('album' in t.keys()):
            iAlbum = t['album']
        if('time' in t.keys()):
            iTime = t['time']

        self.updateTrack(iName, iArtist, iAlbum, 
                         iTime, self.startTime)

    def updateTrack(self, name, artist, album, time, startTime):
        # make sure the track has actually changed
        if( (artist != self.trackArtist) or (name != self.trackName) ):
            self.trackArtist = artist
            self.trackName  = name
            self.trackAlbum = album
            self.trackTime = time

            for plugin in pluginList:
                try:
                    pluginList[plugin].logTrack(name, artist, album,    
                                                time, startTime)
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
