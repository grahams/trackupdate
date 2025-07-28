# Copyright (c) 2024 Sean M. Graham <www.sean-graham.com>
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
import sys
import configparser
import logging
import uuid

import time
import datetime
from datetime import date

class HugoBlogTarget(Target):
    pluginName = "Hugo Blog Post Writer"
    enableArchive = True
    showArtist = ""
    showTitle = ""

    episodeNumber = None
    month = None
    day = None
    suffix = None
    year = None
    baseFilename = None
    filePath = ""
    archiveURL = ""
    categories = []
    tags = []
    description = ""
    draft = False

    hugoFile = None
    trackCount = 0

    def __init__(self, config, episode, episodeDate):
        self.episodeNumber = episode
        if(episodeDate):
            self.episodeDate = episodeDate
        
        # Initialize as disabled by default
        self.enabled = False
        
        # read config entries
        try:
            self.filePath = config.get('ListCommon', 'filePath')
            self.archiveURL = config.get('ListCommon', 'archiveURL')
            self.showArtist = config.get('ListCommon', 'showArtist')
            self.showTitle = config.get('ListCommon', 'showTitle')
            
            # Optional Hugo-specific config
            try:
                self.categories = config.get('HugoBlogTarget', 'categories').split(',')
                self.categories = [cat.strip() for cat in self.categories if cat.strip()]
            except configparser.NoOptionError:
                self.categories = ['music', 'podcast']
                
            try:
                self.tags = config.get('HugoBlogTarget', 'tags').split(',')
                self.tags = [tag.strip() for tag in self.tags if tag.strip()]
            except configparser.NoOptionError:
                self.tags = []
                
            try:
                self.description = config.get('HugoBlogTarget', 'description')
            except configparser.NoOptionError:
                self.description = ""
                
            try:
                self.draft = config.getboolean('HugoBlogTarget', 'draft')
            except configparser.NoOptionError:
                self.draft = False
                
        except configparser.NoSectionError:
            logging.error("HugoBlogTarget: No [HugoBlogTarget] section in config")
            return
        except configparser.NoOptionError:
            logging.error("HugoBlogTarget: Missing required values in config")
            return

        # Ensure filePath ends with /
        if(self.filePath.endswith("/") != True):
            self.filePath += "/"

        self.filePath = os.path.expanduser(self.filePath)

        # Create filename in format: episode-522-july-21th-2025.md
        self.month = self.episodeDate.strftime("%B").lower()
        self.day = self.episodeDate.day
        
        # Add ordinal suffix to day
        if 4 <= self.day <= 20 or 24 <= self.day <= 30:
            self.suffix = "th"
        else:
            self.suffix = ["st", "nd", "rd"][self.day % 10 - 1]
            
        self.year = self.episodeDate.year
        self.baseFilename = f"episode-{self.episodeNumber}-{self.month}-{self.day}{self.suffix}-{self.year}"
        
        # Update archive URL if provided
        if self.archiveURL:
            archiveDate = '{dt:%Y}{dt:%m}{dt:%d}'.format(dt=self.episodeDate)
            self.archiveURL = f"{self.archiveURL}{archiveDate}.mp3"

        # Generate Hugo front matter
        frontMatter = self.generateFrontMatter()
        
        # Open file and write front matter
        try:
            self.hugoFile = open(self.filePath + self.baseFilename + '.md', 'w+')
            self.logToFile(self.hugoFile, frontMatter)
            
            # Add content header
            contentHeader = f"\n# Episode {self.episodeNumber} - {self.getLongDate()}\n\n"
            
            contentHeader += f"{{{{< mixcloud id=\"dosburros/{self.baseFilename}\" >}}}}\n\n"
                
            contentHeader += "## Track Listing\n\n"
            contentHeader += "| Song | Artist | Album |\n"
            contentHeader += "|------|--------|-------|\n"
            
            self.logToFile(self.hugoFile, contentHeader)
            
            # Mark as enabled only if everything succeeded
            self.enabled = True
            
        except Exception as e:
            logging.error(f"HugoBlogTarget: Failed to create file: {e}")
            if self.hugoFile:
                self.hugoFile.close()
                self.hugoFile = None
            return

        return

    def generateFrontMatter(self):
        """Generate Hugo front matter with metadata"""
        # Format date in ISO 8601 format with timezone for Hugo
        isoDate = self.episodeDate.strftime("%Y-%m-%dT%H:%M:%S")

        podcast_file = self.episodeDate.strftime('%Y%m%d') + '.mp3'
        
        frontMatter = "---\n"
        frontMatter += f"title: \"Episode {self.episodeNumber} - {self.getLongDate()}\"\n"
        frontMatter += f"date: \"{isoDate}\"\n"
        frontMatter += f"author: \"{self.showArtist}\"\n"
        frontMatter += f"episode_type: full\n"
        frontMatter += f"explicit: \"1\"\n"
        frontMatter += f"guid: \"{str(uuid.uuid4())}\"\n"
        frontMatter += f"podcast_bytes: \"foo\"\n"
        frontMatter += f"podcast_duration: \"foo\"\n"
        frontMatter += f"podcast_file: \"{podcast_file}\"\n"
        
        # Generate URL in format: /2025/07/episode-522-july-21th-2025/
        frontMatter += f"url: \"/{self.year}/{self.month}/{self.baseFilename}/\"\n"
        
        if self.description:
            frontMatter += f"description: \"{self.description}\"\n"
        
        if self.categories:
            frontMatter += f"categories: {self.categories}\n"
            
        if self.tags:
            frontMatter += f"tags: {self.tags}\n"
            
        frontMatter += f"draft: {str(self.draft).lower()}\n"
        frontMatter += "---\n"
        
        return frontMatter

    def logTrack(self, track, startTime):
        if not self.enabled or not self.hugoFile:
            return
            
        if( track.ignore is not True ):
            self.trackCount += 1
            
            # Escape any pipe characters in track data to avoid breaking markdown table
            title = track.title.replace('|', '\\|') if track.title else ''
            artist = track.artist.replace('|', '\\|') if track.artist else ''
            album = track.album.replace('|', '\\|') if track.album else ''
            
            trackText = f"| {title} | {artist} | {album} |\n"
            
            self.logToFile(self.hugoFile, trackText)

        return

    def close(self):
        if not self.enabled or not self.hugoFile:
            return
            
        print("Closing Hugo Blog File...")
        
        # Add footer with track count
        footer = f"\n\n*Total tracks: {self.trackCount}*\n"
        self.logToFile(self.hugoFile, footer)
        
        self.hugoFile.close()
        
        return 