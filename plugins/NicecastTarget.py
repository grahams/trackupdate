from Target import Target

import os
from datetime import date

class NicecastTarget(Target):
    nowPlayingFilePath = os.path.expanduser('~/Library/Application Support/Nicecast/NowPlaying.txt')
    pluginName = "Nicecast Track Updater"

    def __init__(self, config, episode):
        return

    def close(self):
        os.remove(self.nowPlayingFilePath)

    def logTrack(self, title, artist, album, time):
        fh = open(self.nowPlayingFilePath, 'w')
        fh.write("Title: " + title + '\n')
        fh.write("Artist: " + artist + '\n')
        fh.write("Album: " + album + '\n')
        fh.write("Time: " + time + '\n')
        fh.close()
