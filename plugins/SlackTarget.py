# Copyright (c) 2017 Sean T. Hammond
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
import ConfigParser
import os
import string
import subprocess

class SlackTarget(Target):
    nowPlayingFilePath = os.path.expanduser('~/Library/Application Support/Nicecast/NowPlaying.txt')
    pluginName = "Slack Track Updater"

    # config values
    slackChannel = "" #what slack channel do you want the track data announced in
    slackWebHookUrl = "" #this is the slack webhook url. See https://api.slack.com/incoming-webhooks for more info
    slackEmoji = "" #you can prefix the text sent to slack with an emoji. it only appears if the viewer's message display is set to "clean" in preferences
    slackAnnouncementPrefix = "" #this should be the "user name", but we're using it almost like moo-like a stage-talk

    def __init__(self, config, episode):
        self.theJSONPayload = '{"channel": "%s", "username": %s, "text": "%s", "icon_emoji": ":%s:"}'
        try:
            self.slackChannel = config.get('SlackTarget', 'slackChannel')
            self.slackWebHookUrl = config.get('SlackTarget', 'webhookURL')
            self.slackEmoji = config.get('SlackTarget', 'emojiName')
            self.slackAnnouncementPrefix = config.get('SlackTarget', 'announcementPrefix')
        except ConfigParser.NoSectionError:
            print("SlackTarget: No [SlackTarget] section in config")
            return
        except ConfigParser.NoOptionError:
            print("SlackTarget: Missing values in config")
            return

    def close(self):
        return

    def logTrack(self, title, artist, album, time, startTime):
        #make sure the title and artist don't have an apostrophe or quote in them
        theTitle=string.replace(title, "\'", "\u0027")
        theTitle=string.replace(theTitle, "\'", "\u0022")
        theArtist=string.replace(artist, "\'", "\u0027")
        theArtist=string.replace(theArtist, "\"", "\u0022")
        theTrackString = "_%s_ by %s" % (theTitle, theArtist)
        thePayload = self.theJSONPayload % (self.slackChannel, self.slackAnnouncementPrefix, theTrackString, self.slackEmoji)
        theArgument = "curl -s -X POST --data-urlencode 'payload=%s'  %s" % (thePayload, self.slackWebHookUrl)
        subprocess.check_output(theArgument, shell=True)


