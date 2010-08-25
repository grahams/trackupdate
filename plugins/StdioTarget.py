from Target import Target

import os

class StdioTarget(Target):
    pluginName = "stdio Track Updater"

    def __init__(self, config, episode):
        return

    def close(self):
        return

    def logTrack(self, title, artist, album, time):
        print artist + " - " + title
