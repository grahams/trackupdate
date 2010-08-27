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

import os
import ConfigParser;

# Since the user may not have python-twitter installed, and I didn't want it
# to fail ugly in that case, we do some exception handling
importSuccessful = True

try:
    import twitter
except ImportError:
    print("TwitterTarget: python-twitter module not installed, check out:") 
    print("TwitterTarget:     http://code.google.com/p/python-twitter/")
    importSuccessful = False

class TwitterTarget(Target):
    pluginName = "Twitter Track Updater"
    initTweet = None
    closeTweet = None

    def __init__(self, config, episode):
        if( importSuccessful == True ):
            try:
                username = config.get('twitter', 'username')
                password = config.get('twitter', 'password')
            except ConfigParser.NoSectionError:
                print("TwitterTarget: No [twitter] section in config")
                return
            except ConfigParser.NoOptionError:
                print("TwitterTarget: Username/Password unspecified in config")
                return

            # this is an optional config value containing a tweet to be 
            # sent on init
            try:
                self.initTweet = config.get('twitter', 'initTweet')
            except ConfigParser.NoSectionError:
                pass
            except ConfigParser.NoOptionError:
                pass

            # this is an optional config value containing a tweet to be 
            # sent on close
            try:
                self.closeTweet = config.get('twitter', 'closeTweet')
            except ConfigParser.NoSectionError:
                pass
            except ConfigParser.NoOptionError:
                pass

            self.api = twitter.Api(username=username, password=password)
            if(self.initTweet != None):
                self.api.PostUpdate(self.initTweet)
        return

    def close(self):
        if( importSuccessful == True ):
            if( self.api != None ):
                if(self.closeTweet != None):
                    self.api.PostUpdate(self.closeTweet)
                return

    def logTrack(self, title, artist, album, time):
        if( importSuccessful == True ):
            if( self.api != None ):
                tweet = artist + " - " + title

                if( len(tweet) > 140 ):
                    self.api.PostUpdate(tweet[0:140])
                else:
                    self.api.PostUpdate(tweet)
