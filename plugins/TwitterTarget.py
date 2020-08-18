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
import os

import logging

# Since the user may not have python-twitter installed, and I didn't want it
# to fail ugly in that case, we do some exception handling
importSuccessful = True

try:
    import twitter
except ImportError:
    print("TwitterTarget: twitter module missing, check out:") 
    print("TwitterTarget:     https://pypi.python.org/pypi/python-twitter/3.3")
    importSuccessful = False

class TwitterTarget(Target):
    logger = logging.getLogger("twitter updater")
    
    pluginName = "Twitter Track Updater"
    initTweet = None
    closeTweet = None

    OAuthConsumerKey = None
    OAuthConsumerSecret = None
    OAuthUserToken = None
    OAuthUserTokenSecret = None
    t = None

    def __init__(self, config, episode, episodeDate):
        if( importSuccessful == True ):
            try:
                self.OAuthConsumerKey = config.get('TwitterTarget', 'OAuthConsumerKey')
                self.OAuthConsumerSecret = config.get('TwitterTarget', 'OAuthConsumerSecret')
            except configparser.NoSectionError:
                logger.error("TwitterTarget: No [TwitterTarget] section in config")
                return
            except configparser.NoOptionError:
                logger.error("TwitterTarget: OAuth Consumer Key/Secret unspecified in config")
                return

            # try to read the OAuth user tokens from the config file,
            # otherwise obtain new tokens.
            try:
                self.OAuthUserToken = config.get('TwitterTarget', 'OAuthUserToken')
                self.OAuthUserTokenSecret = config.get('TwitterTarget', 'OAuthUserTokenSecret')
            except configparser.NoSectionError:
                logger.error("TwitterTarget: No [TwitterTarget] section in config")
                return
            except configparser.NoOptionError:
                logger.error("TwitterTarget: Need to obtain OAuth Authorization.")
                self.obtainAuth()

            # this is an optional config value containing a tweet to be 
            # sent on init
            try:
                self.initTweet = config.get('TwitterTarget', 'initTweet')
            except configparser.NoSectionError:
                pass
            except configparser.NoOptionError:
                pass

            # this is an optional config value containing a tweet to be 
            # sent on close
            try:
                self.closeTweet = config.get('TwitterTarget', 'closeTweet')
            except configparser.NoSectionError:
                pass
            except configparser.NoOptionError:
                pass

            self.t = twitter.Api(consumer_key=self.OAuthConsumerKey, 
                                 consumer_secret=self.OAuthConsumerSecret,
                                 access_token_key=self.OAuthUserToken, 
                                 access_token_secret=self.OAuthUserTokenSecret) 


            if(self.initTweet != None):
                try:
                    self.t.PostUpdate(self.initTweet)
                except twitter.TwitterError:
                    logger.error("twitter error")
        return

    def close(self):
        if( importSuccessful == True ):
            if( self.t != None ):
                if(self.closeTweet != None):
                    print("Posting farewell to Twitter...")
                    try:
                        self.t.PostUpdate(self.closeTweet)
                    except twitter.TwitterError:
                        logger.error("twitter error")
                return

    def logTrack(self, track, startTime):
        if( track.ignore is not True):
            if( importSuccessful == True ):
                if( self.t != None ):
                    tweet = track.artist + " - " + track.title

                    tweet = tweet[0:280]

                    try:
                        if(track.artwork != "/dev/null/"):
                            self.t.PostUpdate(tweet,
                                              media=track.getArtworkPath())
                        else:
                            self.t.PostUpdate(tweet)
                    except twitter.TwitterError:
                        logger.error("twitter error")

    def obtainAuth(self):
        import urlparse
        import oauth2 as oauth

        consumer_key = self.OAuthConsumerKey
        consumer_secret = self.OAuthConsumerSecret

        request_token_url = 'https://twitter.com/oauth/request_token'
        access_token_url = 'https://twitter.com/oauth/access_token'
        authorize_url = 'https://twitter.com/oauth/authorize'

        consumer = oauth.Consumer(consumer_key, consumer_secret)
        client = oauth.Client(consumer)

        # Step 1: Get a request token. This is a temporary token that is used for 
        # having the user authorize an access token and to sign the request to obtain 
        # said access token.

        resp, content = client.request(request_token_url, "GET")
        if resp['status'] != '200':
            raise Exception("Invalid response %s." % resp['status'])

        request_token = dict(urlparse.parse_qsl(content))

        print("Request Token:")
        print(f"    - oauth_token        = {request_token['oauth_token']}")
        print(f"    - oauth_token_secret = {request_token['oauth_token_secret']}")
        print("\n")

        # Step 2: Redirect to the provider. Since this is a CLI script we do not 
        # redirect. In a web application you would redirect the user to the URL
        # below.

        print("Go to the following link in your browser:")
        print(f"{authorize_url}?oauth_token={request_token['oauth_token']}")
        print("\n")

        # After the user has granted access to you, the consumer, the provider will
        # redirect you to whatever URL you have told them to redirect to. You can 
        # usually define this in the oauth_callback argument as well.
        accepted = 'n'
        while accepted.lower() == 'n':
            accepted = raw_input('Have you authorized me? (y/n) ')
        oauth_verifier = raw_input('What is the PIN? ')

        # Step 3: Once the consumer has redirected the user back to the oauth_callback
        # URL you can request the access token the user has approved. You use the 
        # request token to sign this request. After this is done you throw away the
        # request token and use the access token returned. You should store this 
        # access token somewhere safe, like a database, for future use.
        token = oauth.Token(request_token['oauth_token'],
            request_token['oauth_token_secret'])
        token.set_verifier(oauth_verifier)
        client = oauth.Client(consumer, token)

        resp, content = client.request(access_token_url, "POST")
        access_token = dict(urlparse.parse_qsl(content))

        self.OAuthUserToken = access_token['oauth_token']
        self.OAuthUserTokenSecret = access_token['oauth_token_secret']

        print("\n===========================")
        print("To prevent this authorization process next session, " + 
              "add the following lines to the [twitter] section of " +
              "your .trackupdaterc:")

        print("OAuthUserToken: " + self.OAuthUserToken)
        print("OAuthUserTokenSecret: " + self.OAuthUserTokenSecret)
        print("===========================\n")

