# Copyright (c) 2017-2020 Sean T. Hammond, Sean M. Graham
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
import string
import subprocess
import json
import requests

class SlackTarget(Target):
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
        except configparser.NoSectionError:
            print("SlackTarget: No [SlackTarget] section in config")
            return
        except configparser.NoOptionError:
            print("SlackTarget: Missing values in config")
            return

    def close(self):
        return

    def logTrack(self, title, artist, album, time, artwork, startTime, ignore):
        if( ignore is not True):
            payload = {'channel': self.slackChannel,
                       'username': self.slackAnnouncementPrefix,
                       'text': f'_{title}_ by {artist}',
                       'icon_emoji': self.slackEmoji}

            requests.post(self.slackWebHookUrl, json=payload)
