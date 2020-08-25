import sqlite3
import datetime
from datetime import timedelta

deltaSeconds = -29
episodeNumber = 320
sourceDBPath = "/Users/grahams/src/trackupdate/db/trackupdate.sqlite"
destDBPath = f"episode-{episodeNumber}.sqlite"

sourceConn = sqlite3.connect(sourceDBPath)
sourceCursor = sourceConn.cursor()

destConn = sqlite3.connect(destDBPath)
destCursor = destConn.cursor()

destCursor.execute('''
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

for row in sourceCursor.execute('''
        SELECT * FROM trackupdate 
        WHERE episodeNumber = '%s'
        ORDER BY startTime''' % episodeNumber):

    episodeNumber = row[0]
    uniqueId = row[1]
    title = row[2]
    artist = row[3]
    album = row[4]
    length = row[5]
    artworkFileName = row[6]
    sTime = row[7]
    ignore = row[8]

    beforeTime = datetime.datetime.fromisoformat(sTime)
    sTime = beforeTime + timedelta(seconds = deltaSeconds)

    destCursor.execute("INSERT INTO trackupdate VALUES (?,?,?,?,?,?,?,?,?)",
                       (episodeNumber,
                       uniqueId,
                       title,
                       artist,
                       album,
                       length,
                       artworkFileName,
                       sTime,
                       ignore))
    destConn.commit()


sourceConn.close()
destConn.close()

