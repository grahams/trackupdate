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
import logging
import uuid
import time

class SlackTarget(Target):
    pluginName = "Slack Track Updater"
    logger = logging.getLogger("slack updater")

    slackWebHookUrl = "" # https://api.slack.com/incoming-webhooks

    def __init__(self, config, episode, episodeDate):
        if(episodeDate):
            self.episodeDate = episodeDate
        
        try:
            self.slackWebHookUrl = config.get('SlackTarget', 'webhookURL')
        except configparser.NoSectionError:
            self.logger.error("SlackTarget: No [SlackTarget] section in config")
            return
        except configparser.NoOptionError:
            self.logger.error("SlackTarget: Missing values in config")
            return

    def close(self):
        return

    def logTrack(self, track, startTime):

        artworkUrl = None
        postString = f'{track.title} by {track.artist}'

        blocks = [{
            "type": "section",
            "block_id": str(uuid.uuid4()),
            "fields": [
            {
                    "type": "mrkdwn",
                    "text": "*Song*"
            },
            {
                    "type": "mrkdwn",
                    "text": track.title
            },
            {
                    "type": "mrkdwn",
                    "text": "*Artist*"
            },
            {
                    "type": "mrkdwn",
                    "text": track.artist
            },
            {
                    "type": "mrkdwn",
                    "text": "*Album*"
            },
            {
                    "type": "mrkdwn",
                    "text": track.album
            }
            ]
        }]

        if(track.artworkURL != "" and track.artworkURL != None):
            blocks[0]["accessory"] = {
                        "type": "image",
                        "image_url": track.artworkURL,
                        "alt_text": f"Cover image of {postString}"
            }

        if( track.ignore is not True):
            payload = { 'text': postString, 'blocks': blocks }

            self.logger.debug("sending payload: " + json.dumps(payload))

            r = requests.post(self.slackWebHookUrl, json=payload)
            self.logger.debug("post status: " + str(r.status_code))
            self.logger.debug("post response: " + str(r.text))
