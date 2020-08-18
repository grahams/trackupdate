# Copyright (c) 2020 Sean M. Graham <www.sean-graham.com>
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

import time
import datetime
from datetime import date

import sqlite3

class SqliteTarget(Target):
    pluginName = "Sqlite Writer"
    episodeNumber = -1
    conn = None
    c = None

    def __init__(self, config, episode, episodeDate):
        self.episodeNumber = episode
        dbPath = ""

        # read config entries
        try:
            dbPath = config.get('SqliteTarget', 'dbPath')
        except configparser.NoSectionError:
            print("SqliteTarget: No [SqliteTarget] section in config")
            return
        except configparser.NoOptionError:
            print("SqliteTarget: Missing values in config")
            return

        dbPath = os.path.expanduser(dbPath)
        self.conn = sqlite3.connect(dbPath)
        self.c = self.conn.cursor()

        self.createTables(self.c)

        return

    def createTables(self, c):
        c.execute('''
            CREATE TABLE IF NOT EXISTS trackupdate (
            episodeNumber integer NOT NULL,
            uniqueId char(128),
            title char(128),
            artist char(128),
            album char(128),
            length char(128),
            artworkFileName text(128),
            startTime timestamp(128),
            "ignore" integer(128) NOT NULL DEFAULT(0)
            );''')


    def logTrack(self, track, startTime):
        debool = (0,1)[track.ignore]
        self.c.execute("INSERT INTO trackupdate VALUES (?,?,?,?,?,?,?,?,?)",
                       (self.episodeNumber, 
                        track.uniqueId,
                        track.title,
                        track.artist,
                        track.album,
                        track.length,
                        track.artwork,
                        datetime.datetime.now(),
                        debool))

        self.conn.commit()

        return

    def close(self):
        print("Closing database...")

        self.conn.close()

        return
