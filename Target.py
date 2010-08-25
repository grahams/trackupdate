
class Target:
    pluginName = "Base Class"

    def __init__(self, config, episode):
        print "If this were a real plugin we would do some initalization here"

    def close(self):
        print "If this were a real plugin we would do some destruction here"

    def logTrack(self, title, artist, album, time):
        print "If this were a real plugin it would do something profound with this data:"

        print "title: " + title
        print "artist: " + artist
        print "album: " + album
        print "time: " + time
