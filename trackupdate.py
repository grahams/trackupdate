#!/usr/bin/env python3

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
import configparser
import glob
import logging
import subprocess
import json
import traceback
import sqlite3
import requests
import re

from urllib.parse import quote
from datetime import datetime,date
from operator import attrgetter
from Track import Track
from pathlib import Path

pluginList = []

class TrackUpdate(object):
    introAlbum = ""

    currentTrack = Track(None,None,None,None,None,None,None)

    coverImagePath = ""
    coverImageBaseURL = ""
    pollScriptPath = ""
    episodeNumber = "XX"
    archiveDate = None
    useDatabase = False
    pollTime = 10
    startTime = -1
    useStopValues = False
    stopTitle = ""
    stopArtist = ""
    stopAlbum = ""
    stopArtwork = ""
    ignoreAlbum = None
    pluginPattern = "*.py"
    dbPath = None
    conn = None
    c = None
    logger = logging.getLogger()

    def usage(self):
        print( "Usage: trackupdate.py [arguments]" )
        print( """
This is a simple script which polls Apple Music for track info every 
(default) 10 seconds and gives that information to plugin scripts to act 
upon (for instance, announcing the track information to Slack, or updating
the metadata in Audio Hijack's Broadcast module)

Arguments:
    -v  --verbose     you are lonely and want trackupdate to talk more
    -e  --episode     the episode number (optional, used by some plugins)
    -t  --polltime    the time to wait between polling iTunes
    -h  --help        show this help page
    -p  --pattern     plugin filename pattern (optional, defaults to '*.py')
    -a  --archive     use the sqlite db as the track source

Example:
    ./trackupdate.py -e 42 -t 5 -v
    """)

    def __init__(self,argv):
        config = None
        self.logger.setLevel(logging.WARNING)

        # process config file
        if not os.path.isfile(os.path.expanduser('~/.trackupdaterc')):
            self.logger.warning("Warning: no config .trackupdaterc file.")

        config = configparser.ConfigParser()
        config.read(os.path.expanduser('~/.trackupdaterc'))

        try:
            self.introAlbum = config.get('trackupdate', 'introAlbum')
            self.pollTime = int(config.get('trackupdate', 'pollTime'))
            self.useStopValues = config.get('trackupdate', 'useStopValues')
            self.stopTitle = config.get('trackupdate', 'stopTitle')
            self.stopArtist = config.get('trackupdate', 'stopArtist')
            self.stopAlbum = config.get('trackupdate', 'stopAlbum')
            self.stopArtwork = config.get('trackupdate', 'stopArtwork')
            self.ignoreAlbum = config.get('trackupdate', 'ignoreAlbum')
            self.coverImagePath = config.get('trackupdate', 'coverImagePath')
            self.coverImageBaseURL = config.get('trackupdate', 'coverImageBaseURL')
            self.pollScriptPath = config.get('trackupdate', 'pollScriptPath')
            self.dbPath = config.get('SqliteTarget', 'dbPath')
            
        except configparser.NoSectionError:
            self.logger.error("Warning: Invalid config file, no [trackupdate] section.")
            pass
        except configparser.NoOptionError:
            self.logger.error("[trackupdate]: Missing values in config")
            return

        self.coverImagePath = os.path.expanduser(self.coverImagePath) 

        # process command-line arguments
        if(len(argv) > 0):
            try:
                opts, args = getopt.getopt(sys.argv[1:], "h:e:t:p:va", ["help",
                                           "episode=", "polltime=", 
                                           "pattern=", "verbose", "archive"])
            except (getopt.GetoptError) as err:
                # print help information and exit:
                self.logger.error(str(err)) # will print something like 
                                       # "option -a not recognized"
                self.usage()
                sys.exit(2)

            for o, a in opts:
                if o in ("-e", "--episode"):
                    self.episodeNumber = a
                elif o in ("-a", "--archive"):
                    self.useDatabase = True
                elif o in ("-t", "--polltime"):
                    a = int(a)
                    if(a <= 0):
                        a = 1

                    self.pollTime = a
                elif o in ("-p", "--pattern"):
                    self.logger.debug("Plugin pattern set to: " + a)
                    self.pluginPattern = a
                elif o in ("-v", "--verbose"):
                    # remove any logging handlers created by logging before
                    # BasicConfig() is called
                    if(self.logger.handlers):
                        for handler in self.logger.handlers:
                            self.logger.removeHandler(handler)

                    self.logger.setLevel(logging.DEBUG)
                    logging.debug("Starting up. Press Ctrl-C to stop.")
                elif o in ("-h", "--help"):
                    self.usage()
                    sys.exit()
                else:
                    assert False, "unhandled option"

        # default stopArtwork if empty
        if(self.stopArtwork == ""):
            todayName = date.today().strftime("%Y%m%d.jpg")
            self.stopArtwork = todayName

        self.logger.debug(f"self.stopArtwork is {self.stopArtwork}")

        try:
            if(self.useDatabase):
                self.logger.debug("In archive mode, reading from sqlite db")
                self.logger.debug("Episode #: %s" % str(self.episodeNumber))
                self.logger.debug("Time between polling: %i" % self.pollTime)

                if(self.episodeNumber == "XX"):
                    self.logger.error('Episode number ("-e/--episode") required for archive mode')
                else:
                    self.dbPath = os.path.expanduser(self.dbPath)
                    self.conn = sqlite3.connect(self.dbPath)
                    self.c = self.conn.cursor()

                    # retrieve the first date 
                    for row in self.c.execute("SELECT startTime FROM trackupdate WHERE episodeNumber = '%s' ORDER BY startTime LIMIT 1" % self.episodeNumber):
                        sTime = datetime.fromisoformat(row[0])
                        self.logger.debug("Archive Date: " + str(sTime))
                        self.archiveDate = sTime

                    self.loadPlugins(config)

                    self.archiveLoop()
            else:
                self.logger.debug("In live mode, reading from Applescript")
                self.logger.debug("Episode #: %s" % str(self.episodeNumber))
                self.logger.debug("Time between polling: %i" % self.pollTime)

                self.loadPlugins(config)
                self.liveLoop()
        except (KeyboardInterrupt,SystemExit):
            self.cleanUp()

    def liveLoop(self):
        previousTrack = None

        if(self.introAlbum != ""):
            while(1):
                if(self.startTime==-1):
                    try:
                        trackJson = subprocess.check_output(["util/swinsian-track-grabber"])
                        track = json.loads(trackJson)

                    except subprocess.CalledProcessError:
                        self.logger.error("osascript failed, skipping track")
                        continue
                    except json.decoder.JSONDecodeError:
                        self.logger.error("JSON decode, skipping track")
                        continue

                    album = None

                    if('trackAlbum' in track.keys()):
                        album = track['trackAlbum']
                    

                    if((len(track) == 0) or (album == self.introAlbum)):
                        time.sleep(self.pollTime)
                    else:
                        break
                else:
                    break

        while(1):
            track = json.loads(subprocess.check_output(["util/swinsian-track-grabber"],
                                                        text=True))

            # this is jank but don't keep updating the track unnecessarily
            if(previousTrack != track):
                previousTrack = track

                if(len(track) > 0):
                    self.processCurrentTrack(track)
                elif(self.useStopValues == 'True'):
                    stopTrack = Track(self.stopTitle, 
                                        self.stopArtist, 
                                        self.stopAlbum, 
                                        "9:99",
                                        None,
                                        "", 
                                        False)
                    self.updateTrack(stopTrack, datetime.now())

            time.sleep(self.pollTime)

    def searchArtwork(self, trackName, searchArtist, searchAlbum):
        url100 = None
        url500 = None

        try:
            searchTerm = quote(f"{searchArtist} {trackName}")
            searchUrl = f'https://itunes.apple.com/search?term={searchTerm}&entity=song&limit=1'
            trackSearch = requests.get(searchUrl).json()

            if(trackSearch['resultCount'] > 0):
                url100 = trackSearch["results"][0]["artworkUrl100"]
                url500 = re.sub(r'100x100', '500x500', url100)
        except requests.exceptions.RequestException as e:
            print(f"Cover image search failed: {e}")
        except json.JSONDecodeError as e:
            print(f"Cover image JSON decode failed: {e}")

        return url500

    def archiveLoop(self):
        for row in self.c.execute("SELECT * FROM trackupdate WHERE episodeNumber = '%s' ORDER BY startTime" % self.episodeNumber):
            episodeNumber = row[0]
            uniqueId = row[1]
            title = row[2]
            artist = row[3]
            album = row[4]
            length = row[5]
            sTime = row[6]
            ignore = row[7]
            artworkUrl = row[8]

            t = Track(title,
                        artist,
                        album,
                        length,
                        artworkUrl,
                        uniqueId,
                        ignore)
            
            sTime = datetime.fromisoformat(sTime)
            self.updateTrack(t,sTime)

        self.cleanUp()

    def cleanUp(self):
        self.logger.debug("Exiting...")

        for plugin in pluginList:
            try:
                plugin.close()
            except Exception as e:
                self.logger.error(plugin.pluginName + ": Error trying to close target")
                self.logger.error(''.join(traceback.format_tb(sys.exc_info()[2])))
    

    def processCurrentTrack(self, t):
        iArtist = ""
        iName = ""
        iAlbum = ""
        iLength = ""
        iId = ""

        if('trackArtist' in t.keys()):
            iArtist = t['trackArtist']
        if('trackName' in t.keys()):
            iName = t['trackName']
        if('trackAlbum' in t.keys()):
            iAlbum = t['trackAlbum']
        if('trackLength' in t.keys()):
            iLength = t['trackLength']
        if('trackId' in t.keys()):
            iId = t['trackId']

        artworkUrl = self.searchArtwork(iName,iArtist,iAlbum)

        if(artworkUrl == None):
            self.logger.debug("No artwork found in search, using default")
            artworkUrl = f"{self.coverImageBaseURL}/{self.stopArtwork}"

        track = Track(iName, 
                      iArtist, 
                      iAlbum, 
                      iLength, 
                      artworkUrl,
                      iId, 
                      False)

        self.updateTrack(track, datetime.now())

    def updateTrack(self, track, startTime):
        # make sure the track has actually changed
        if( (track.artist != self.currentTrack.artist) or 
            (track.title != self.currentTrack.title) ):

            self.currentTrack = track
            track.ignore = False

            if( track.album == self.ignoreAlbum ):
                track.ignore = True

            for plugin in pluginList:
                try:
                    plugin.logTrack(track, startTime)
                except Exception as e:
                    self.logger.error(str(plugin) + ": Error trying to update track")
                    self.logger.error(''.join(traceback.format_tb(sys.exc_info()[2])))

    def loadPlugins(self, config):
        self.logger.debug("Loading plugins...")

        scriptPath = os.path.split(os.path.abspath(__file__))[0]
        
        sys.path.append(scriptPath)
        sys.path.append(scriptPath + "/plugins/")
        pluginNames = glob.glob(scriptPath + "/plugins/" + self.pluginPattern)
        for x in pluginNames:
            className = x.replace(".py","").replace(scriptPath + "/plugins/","")
            enabled = 'False'

            # if the .rc doesn't define whether it is enabled, defaults to False
            try:
                enabled = config.get(className, 'enabled')
            except configparser.NoSectionError:
                enabled = 'False'
            except configparser.NoOptionError:
                enabled = 'False'

            if(enabled=='False'):
                self.logger.debug("Skipping plugin '%s'." % className)
            else:
                self.logger.debug("Loading plugin '%s'...." % className)

                # import the module
                mod = __import__(className, globals(), locals(), [''])

                # find the symbol for the class
                cls  = getattr(mod,className)

                if(self.useDatabase and not cls.enableArchive):
                    self.logger.debug(f"{cls.pluginName} Plugin not enabled for archive mode, skipping")
                else:
                    # initialize the plugin
                    o = cls(config, self.episodeNumber, self.archiveDate)

                    # add the plugin to the list
                    pluginList.append(o)

        pluginList.sort(key=attrgetter('priority'), reverse=True)

if __name__ == "__main__":
    trackUpdate = TrackUpdate(sys.argv[1:])
