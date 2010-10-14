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
    from oauth import oauth
    from oauthtwitter import OAuthApi
except ImportError:
    print("TwitterTarget: oauth-python-twitter2 module missing, check out:") 
    print("TwitterTarget:     http://code.google.com/p/oauth-python-twitter2/")
    importSuccessful = False

class TwitterTarget(Target):
    pluginName = "Twitter Track Updater"
    initTweet = None
    closeTweet = None

    OAuthConsumerKey = None
    OAuthConsumerSecret = None
    OAuthUserToken = None
    OAuthUserTokenSecret = None

    def __init__(self, config, episode):
        if( importSuccessful == True ):
            try:
                self.OAuthConsumerKey = config.get('twitter', 'OAuthConsumerKey')
                self.OAuthConsumerSecret = config.get('twitter', 'OAuthConsumerSecret')
            except ConfigParser.NoSectionError:
                print("TwitterTarget: No [twitter] section in config")
                return
            except ConfigParser.NoOptionError:
                print("TwitterTarget: OAuth Consumer Key/Secret unspecified in config")
                return

            # try to read the OAuth user tokens from the config file,
            # otherwise obtain new tokens.
            try:
                self.OAuthUserToken = config.get('twitter', 'OAuthUserToken')
                self.OAuthUserTokenSecret = config.get('twitter', 'OAuthUserTokenSecret')
            except ConfigParser.NoSectionError:
                print("TwitterTarget: No [twitter] section in config")
                return
            except ConfigParser.NoOptionError:
                print("TwitterTarget: Need to obtain OAuth Authorization.")
                self.obtainAuth()

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

            self.api = OAuthApi(self.OAuthConsumerKey,
                                self.OAuthConsumerSecret,
                                self.OAuthUserToken,
                                self.OAuthUserTokenSecret)

            if(self.initTweet != None):
                self.api.UpdateStatus(self.initTweet)
        return

    def close(self):
        if( importSuccessful == True ):
            if( self.api != None ):
                if(self.closeTweet != None):
                    print("Posting farewell to Twitter...")
                    self.api.UpdateStatus(self.closeTweet)
                return

    def logTrack(self, title, artist, album, time):
        if( importSuccessful == True ):
            if( self.api != None ):
                tweet = artist + " - " + title

                if( len(tweet) > 140 ):
                    self.api.UpdateStatus(tweet[0:140])
                else:
                    self.api.UpdateStatus(tweet)

    def obtainAuth(self):
        twitter = OAuthApi(self.OAuthConsumerKey, self.OAuthConsumerSecret)

        # Get the temporary credentials for our next few calls
        temp_credentials = twitter.getRequestToken()

        # User pastes this into their browser to bring back a pin number
        print(twitter.getAuthorizationURL(temp_credentials))

        # Get the pin # from the user and get our permanent credentials
        oauth_verifier = raw_input('What is the PIN? ')
        access_token = twitter.getAccessToken(temp_credentials, oauth_verifier)

        self.OAuthUserToken = access_token['oauth_token']
        self.OAuthUserTokenSecret = access_token['oauth_token_secret']

        print("\n===========================")
        print("To prevent this authorization process next session, " + 
              "add the following lines to the [twitter] section of " +
              "your .trackupdaterc:")

        print("OAuthUserToken: " + self.OAuthUserToken)
        print("OAuthUserTokenSecret: " + self.OAuthUserTokenSecret)
        print("===========================\n")

