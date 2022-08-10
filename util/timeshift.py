import sys
import sqlite3
import argparse
import datetime
import json

from datetime import datetime,timedelta
from tabulate import tabulate


class TimeShift(object):
    tracks = []
    dbPath = "/Users/grahams/src/trackupdate/db/trackupdate.sqlite"

    def __init__(self, argv):
        self.readEpisode(175)
        #self.insertTrack(31, 407, None, "INSERTED", "INSERTOR", "THE INSERTED", "4:20",
                    #False, None)
        #self.writeEpisode(407)
        #self.importJson(175, "/Users/grahams/aatemp/News/20120618.json")
        self.printTable()
        #self.updateTrackRange(39,43,-7)
        #self.writeEpisode(175)

    def readEpisode(self, episodeNumber):
        sourceConn = sqlite3.connect(self.dbPath)
        sourceCursor = sourceConn.cursor()
        firstTime = None

        for row in sourceCursor.execute('''
                SELECT * FROM trackupdate 
                WHERE episodeNumber = '%s'
                ORDER BY startTime''' % episodeNumber):

            track = {}

            track['episodeNumber'] = row[0]
            track['uniqueId'] = row[1]
            track['title'] = row[2]
            track['artist'] = row[3]
            track['album'] = row[4]
            track['length'] = row[5]
            track['sTime'] = datetime.fromisoformat(row[6])
            track['origTime'] = datetime.fromisoformat(row[6])
            track['ignore'] = row[7]
            track['artworkUrl'] = row[8]

            if(firstTime == None):
                firstTime = track['sTime']

            track['elapsedTime'] = str(track['sTime'] - firstTime)

            self.tracks.append(track)

        sourceConn.close()

    def updateTrackRange(self, start, end, deltaSeconds):
        for x in range(start,end):
            track = self.tracks[x]

            track['origTime'] = track['sTime']
            newTime = track['origTime'] + timedelta(seconds = deltaSeconds)
            track['sTime'] = newTime

    def importJson(self, episodeNumber, filePath):
        f = open(filePath)
        data = json.load(f)

        for x in range(len(data)):
            track = data[x]
            self.insertTrack(x, 175, track['uniqueId'], track['trackName'],
                             track['trackArtist'], track['trackAlbum'],
                             track['trackLength'], track['trackDuration'],
                             False, "")


    def insertTrack(self, position, episodeNumber, uniqueId, title, artist, album,
                    length, duration, ignore, artworkUrl):
            if(len(self.tracks) > 0):
                firstTime = self.tracks[0]['sTime']
            else:
                #firstTime = datetime.now()
                firstTime = datetime.fromisoformat("2022-08-07 14:05:11.145024")

            beforeTime = firstTime
            beforeSeconds = 0

            if(position > 0):
                beforeRow = self.tracks[position-1]
                beforeTime = beforeRow['sTime']
                beforeLength = beforeRow['length'].split(':')
                beforeSeconds = (int(beforeLength[0]) * 60) + int(beforeLength[1])

            newTrack = {}

            newTrack['episodeNumber'] = episodeNumber
            newTrack['uniqueId'] = uniqueId
            newTrack['title'] = title
            newTrack['artist'] = artist
            newTrack['album'] = album
            newTrack['length'] = length
            newTrack['duration'] = duration
            newTrack['sTime'] = beforeTime + timedelta(seconds = beforeSeconds)
            newTrack['origTime'] = newTrack['sTime']
            newTrack['ignore'] = ignore
            newTrack['artworkUrl'] = artworkUrl
            newTrack['elapsedTime'] = str(newTrack['sTime'] - firstTime)

            self.tracks.insert(position, newTrack)

            self.updateTrackRange(position+1, len(self.tracks), duration)

    def writeEpisode(self, episodeNumber):
        destConn = sqlite3.connect(dbPath)
        destCursor = destConn.cursor()

        destCursor.execute('''
                CREATE TABLE IF NOT EXISTS trackupdate (
                episodeNumber integer NOT NULL,
                uniqueId char(128),
                title char(128),
                artist char(128),
                album char(128),
                length char(128),
                startTime timestamp(128),
                "ignore" integer(128) NOT NULL DEFAULT(0),
                artworkUrl text(128)
                );''')


        for track in self.tracks:
            destCursor.execute("INSERT INTO trackupdate VALUES (?,?,?,?,?,?,?,?,?)",
                            (track["episodeNumber"],
                                track["uniqueId"],
                                track["title"],
                                track["artist"],
                                track["album"],
                                track["length"],
                                track["sTime"],
                                track["ignore"],
                                track["artworkUrl"]))
            destConn.commit()

        destConn.close()

    def printTable(self):
        dispTracks = [{k: track.get(k, None) for k in ('title', 'artist', 'origTime', 'sTime', 'length')} for track in self.tracks]
        print(tabulate(dispTracks, tablefmt="grid", showindex="always",
                    maxcolwidths=[None, 15, 15, None, None]))


if __name__ == "__main__":
    timeShift = TimeShift(sys.argv[1:])


