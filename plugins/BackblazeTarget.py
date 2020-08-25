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

import logging

from b2sdk.v1 import *

class BackblazeTarget(Target):
    pluginName = "Backblaze Track Updater"
    priority = 100
    logger = logging.getLogger("Backblaze Uploader")

    b2 = None
    bucket = None

    appKey = None
    appKeyId = None
    bucketName = None

    def __init__(self, config, episode, episodeDate):
        try:
            self.appKey = config.get('BackblazeTarget', 'appKey')
            self.appKeyId = config.get('BackblazeTarget', 'appKeyId')
            self.bucketName = config.get('BackblazeTarget', 'bucketName')
        except configparser.NoSectionError:
            self.logger.error("BackblazeTarget: No [BackblazeTarget] section in config")
            return
        except configparser.NoOptionError:
            self.logger.error("BackblazeTarget: Missing option in config")
            return

        info = InMemoryAccountInfo()
        self.b2 = B2Api(info)

        self.logger.debug(f"logging into {self.appKeyId}")
        self.b2.authorize_account("production", self.appKeyId, self.appKey)
        self.bucket = self.b2.get_bucket_by_name(self.bucketName)
        self.logger.debug(f"got bucket {self.bucketName}: {self.bucket}")

        return

    def close(self):
        return

    def logTrack(self, track, startTime):
        if((track.artwork is None) or (track.artwork == "")):
            self.logger.debug(f"{track.title} has no artwork, skipping")

            return
        # check to see if the file already exists in Backblaze
        fileVersions = self.bucket.list_file_versions(track.artwork)

        if(next(fileVersions, None) is not None):
            self.logger.debug(f"{track.artwork} already exists in bucket, skipping")
            return

        self.logger.debug(f"uploading {track.getArtworkPath()}")

        self.bucket.upload_local_file(
            local_file=track.getArtworkPath(),
            file_name=track.artwork)

        self.logger.debug("cover image url: " + self.bucket.get_download_url(track.artwork))

