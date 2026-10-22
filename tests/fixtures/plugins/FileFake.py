from Target import Target

calls = []


class FileFake(Target):
    pluginName = "FileFake"
    priority = 10
    enableArchive = True

    def __init__(self, config, episode, episodeDate):
        calls.append(("init", episode, episodeDate))

    def logTrack(self, track, startTime):
        calls.append(("track", track.title, startTime))

    def close(self):
        calls.append(("close",))
