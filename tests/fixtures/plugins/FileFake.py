from Target import Target

calls = []
tracks = []


class FileFake(Target):
    pluginName = "FileFake"
    priority = 10
    enableArchive = True

    def __init__(self, config, episode, episodeDate):
        calls.append(("init", episode, episodeDate))

    def logTrack(self, track, startTime):
        calls.append(("track", track.title, startTime))
        tracks.append(track)

    def close(self):
        calls.append(("close",))
