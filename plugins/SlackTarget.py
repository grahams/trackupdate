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

    # config values
    slackChannel = "" #what slack channel do you want the track data announced in
    slackWebHookUrl = "" #this is the slack webhook url. See https://api.slack.com/incoming-webhooks for more info
    slackAnnouncementPrefix = "" #this should be the "user name", but we're using it almost like moo-like a stage-talk

    def __init__(self, config, episode):
        try:
            self.slackChannel = config.get('SlackTarget', 'slackChannel')
            self.slackWebHookUrl = config.get('SlackTarget', 'webhookURL')
            self.slackAnnouncementPrefix = config.get('SlackTarget', 'announcementPrefix')
        except configparser.NoSectionError:
            self.logger.error("SlackTarget: No [SlackTarget] section in config")
            return
        except configparser.NoOptionError:
            self.logger.error("SlackTarget: Missing values in config")
            return

    def close(self):
        return

    def logTrack(self, title, artist, album, length, artwork, startTime, ignore):

        artworkUrl = None
        postString = f'{title} by {artist}'

        blocks = [{
            "type": "section",
            "block_id": str(uuid.uuid4()),
            "text": {
                "type": "mrkdwn",
                "text": f"*{self.slackAnnouncementPrefix}*" 
            },
            "fields": [
            {
                    "type": "mrkdwn",
                    "text": "*Song*"
            },
            {
                    "type": "mrkdwn",
                    "text": title
            },
            {
                    "type": "mrkdwn",
                    "text": "*Artist*"
            },
            {
                    "type": "mrkdwn",
                    "text": artist
            },
            {
                    "type": "mrkdwn",
                    "text": "*Album*"
            },
            {
                    "type": "mrkdwn",
                    "text": album
            }
            ]
        }]

        if(artwork.find("Public") > -1):
            artworkStem = artwork.split("Public")[1]
            artworkUrl = f"http://grahams.wtf/public/{artworkStem}"

        if(artworkUrl is not None):
            # Since it takes awhile for the images to propogate, let's make
            # sure they exist first
            waitingUpload = True
            failureCounter = 5

            while(waitingUpload and (failureCounter > 0) ):
                imgRequest = requests.get(artworkUrl)

                self.logger.debug("imgRequest status: " + str(imgRequest.status_code))

                if(imgRequest.status_code == 404):
                    self.logger.debug(f"Cover Image 404: 5s Delay. {failureCounter} left")
                    failureCounter = failureCounter - 1;
                    time.sleep(5);
                else:
                    blocks[0]["accessory"] = {
                                "type": "image",
                                "image_url": artworkUrl,
                                "alt_text": f"Cover image of {postString}"
                    }
                    failureCounter = -1
                    waitingUpload = False

        if( ignore is not True):
            payload = { 'text': postString, 'blocks': blocks }

            self.logger.debug("sending payload: " + json.dumps(payload))

            r = requests.post(self.slackWebHookUrl, json=payload)
            self.logger.debug("post status: " + str(r.status_code))
            self.logger.debug("post response: " + str(r.text))
