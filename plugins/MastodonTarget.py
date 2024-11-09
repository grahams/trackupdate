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
import configparser

import logging

import mastodon
from mastodon import Mastodon

from threading import Thread

import time

class MastodonTarget(Target):
    logger = logging.getLogger("mastodon updater")
    
    pluginName = "Mastodon Track Updater"
    initToot = None
    closeToot = None

    AccessToken = None
    ApiBaseUrl = None

    m = None

    def __init__(self, config, episode, episodeDate):
        try:
            self.AccessToken = config.get('MastodonTarget', 'AccessToken')
            self.ApiBaseUrl = config.get('MastodonTarget', 'ApiBaseUrl')
        except configparser.NoSectionError:
            self.logger.error("MastodonTarget: No [MastodonTarget] section in config")
            return
        except configparser.NoOptionError:
            self.logger.error("MastodonTarget: Auth/Server unspecified in config")
            return

        # this is an optional config value containing a toot to be 
        # sent on init
        try:
            self.initToot = config.get('MastodonTarget', 'initToot')
        except configparser.NoSectionError:
            pass
        except configparser.NoOptionError:
            pass

        # this is an optional config value containing a toot to be 
        # sent on close
        try:
            self.closeToot = config.get('MastodonTarget', 'closeToot')
        except configparser.NoSectionError:
            pass
        except configparser.NoOptionError:
            pass

        self.m = Mastodon(access_token=self.AccessToken,
                          api_base_url=self.ApiBaseUrl)

        if(self.initToot != None):
            try:
                self.m.status_post(self.initToot)
            except mastodon.MastodonError:
                self.logger.error("error posting initial toot")
        return

    def close(self):
        if( self.m != None ):
            if(self.closeToot != None):
                print("Posting farewell to Mastodon...")
                try:
                    self.m.status_post(self.closeToot)
                except mastodon.MastodonError:
                    self.logger.error("error posting farewell toot")
            return

    def logTrack(self, track, startTime):
        tr = track
        st = startTime

        background_thread = Thread(target=self.logTrackInternal,
                                   args=(tr,st,))

        background_thread.start()

    def logTrackInternal(self, track, startTime):
        if( track.ignore is not True):
            if( self.m != None ):
                toot = track.artist + " - " + track.title

                toot = toot[0:500]

                try:
                    self.m.status_post(toot)
                except mastodon.MastodonError:
                    self.logger.error("error tooting track name")
