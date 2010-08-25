from Target import Target

import os
from datetime import date

class WikiTarget(Target):
    wfh = None
    pluginName = "Wiki Text Generator"
    createWikiText = False
    wikiFilePath = ""
    wikiArchiveURL = ""
    episodeNumber = "XX"

    def __init__(self, config, episode):
        self.episodeNumber = episode

        try:
            self.wikiFilePath = config.get('wiki', 'wikiTextDirectory')
            self.wikiArchiveURL = config.get('wiki', 'wikiArchiveURL')
            self.ignoreAlbum = config.get('trackupdate', 'ignoreAlbum')
        except ConfigParser.NoSectionError:
            print("NoSectionError")
            return
        except ConfigParser.NoOptionError:
            print("NoOptionError")
            return

        if(self.wikiFilePath != ""):
            self.createWikiText = True
            self.initWikiFile()

    def close(self):
        if( self.createWikiText == True ):
            self.wfh.write("|}\n")
            self.wfh.close()
        
    def logTrack(self, title, artist, album, time):
        if( self.createWikiText == True ):
            self.wfh.write("|" + title + '\n')
            self.wfh.write("|" + artist + '\n')
            self.wfh.write("|" + album + '\n')
            self.wfh.write("|-\n")

    def initWikiFile(self):
        dateString = date.today().strftime("%Y%m%d")

        filename = os.path.expanduser(self.wikiFilePath + dateString + 
                                      "-wikitext.txt")

        # if the file already exists, delete it
        if(os.access(filename, os.F_OK)):
            os.unlink(filename)

        self.wfh = open(filename, 'a')

        self.wfh.write("=== ")

        if(self.wikiArchiveURL != ""):
            self.wfh.write("[" + date.today().strftime(self.wikiArchiveURL) + " ")

        self.wfh.write("Show #" + self.episodeNumber + " - ")

        # compute the suffix
        day = date.today().day
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = ["st", "nd", "rd"][day % 10 - 1]

        self.wfh.write(date.today().strftime("%A, %B %d"))
        self.wfh.write(suffix)
        self.wfh.write(date.today().strftime(", %Y"))

        if(self.wikiArchiveURL != ""):
            self.wfh.write("]")

        self.wfh.write(" ===\n")

        self.wfh.write("{| border=1 cellspacing=0 cellpadding=5\n")
        self.wfh.write("|'''Song'''\n")
        self.wfh.write("|'''Artist'''\n")
        self.wfh.write("|'''Album'''\n")
        self.wfh.write("|-\n")

