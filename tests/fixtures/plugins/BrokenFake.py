from Target import Target


class BrokenFake(Target):
    pluginName = "BrokenFake"
    priority = 20
    enableArchive = True

    def __init__(self, config, episode, episodeDate):
        pass

    def logTrack(self, track, startTime):
        raise RuntimeError("boom")

    def close(self):
        pass
