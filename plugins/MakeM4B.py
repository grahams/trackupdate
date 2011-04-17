# Copyright (c) 2011 Sean T. Hammond
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

####
#IMPORTANT!
#requires afconvert to work
##/usr/bin/afconvert
#requires ChapterTool to work
##/Applications/GarageBand/Contents/MacOS/ChapterTool

from Target import Target

import os
import time
import datetime
import ConfigParser
import glob
import shutil
import string

from appscript import *

class MakeM4B(Target):
    theFileName = ""
    pluginName = "Enhanced Podcast Maker"
    m4bFolderPath = ""
    mp3FilePath = ""
    chapterToolPath = ""
    withArtwork = True
    runTime = ""
    startTime = -1


    def __init__(self, config, episode):
        try:
            self.m4bFolderPath = config.get('m4b', 'm4bFolder')
            self.mp3FilePath = config.get('m4b', 'mp3FilePath')
            self.chapterToolPath = config.get('m4b', 'chapterToolPath')
            self.withArtwork = config.get('m4b', 'includeArt')
        except ConfigParser.NoSectionError:
            print("%s: No [m4b] section in config") % (self.pluginName)
            return
        except ConfigParser.NoOptionError:
            print("%s: Missing values in config") % (self.pluginName)
            return
        
        #make the destination folder
        self.m4bFolderPath = os.path.expanduser(self.m4bFolderPath+"-Episode "+episode)
        if not os.path.exists(self.m4bFolderPath):
            os.mkdir(self.m4bFolderPath)
        
        #make the desired xml in the folder
        self.theFileName = "Episode_%s.xml"%(str(episode))
        fh = open(self.m4bFolderPath+"/"+self.theFileName, 'w')
        fh.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
        fh.write("<chapters version=\"1\">\n")		
        fh.close()

    def close(self):
        fh = open(self.m4bFolderPath+"/"+self.theFileName, 'a')
        fh.write("</chapters>")
        fh.close()
        
        #convert the archived file made by Nicecast into m4a
        fileDate = time.localtime(self.startTime)
        fileDate = time.strftime("%Y%m%d",fileDate)
        self.mp3FilePath=os.path.expanduser(self.mp3FilePath)
        theMP3File = glob.glob(self.mp3FilePath+"Nicecast Archived Audio "+fileDate+"*.mp3")
        if(len(theMP3File) > 0):
		    theMP3File=theMP3File[-1]
		    theMP3FileName=os.path.split(theMP3File)[1]
		    theAudioBaseName=os.path.splitext(theMP3FileName)[0]
		    print("Making a copy of the archive as an m4a...")
		    theCommand="afconvert -f 'mp4f' -d 'aac ' '%s' '%s/%s.m4a'" % (theMP3File, self.m4bFolderPath, theAudioBaseName)
		    os.system(theCommand)
		    if(os.path.isfile(""+self.m4bFolderPath+"/"+theAudioBaseName+".m4a")):
			    xmlFilePath=self.m4bFolderPath+"/"+self.theFileName
			    inAudioFilePath=self.m4bFolderPath+"/"+theAudioBaseName+".m4a"
			    outAudioFilePath=self.m4bFolderPath+"/"+theAudioBaseName+".m4b"
			    theCommand="'%s' -x '%s' -a '%s' -o '%s'" % (self.chapterToolPath, xmlFilePath, inAudioFilePath, outAudioFilePath)
			    os.system(theCommand)
				
    def logTrack(self, ititle, iartist, ialbum, itime, iart, theStartTime):
        if(theStartTime>0):
            if(self.startTime==-1):self.startTime=theStartTime
            runTimeA = time.time()-theStartTime #runTimeA is reused for artwork names
            runTime=str(datetime.timedelta(seconds=runTimeA))
            
            if(not iart==[]): #iart will be an empty list if there is no art
                theArt=iart[0]
                theArtFormat=iart[1]
            
            #remove '&' characters
            ititle=string.replace(ititle, '&', 'and')
            iartist=string.replace(iartist, '&', 'and')
            ialbum=string.replace(ialbum, '&', 'and')
            
            fh = open(self.m4bFolderPath+"/"+self.theFileName, 'a')
            fh.write("<chapter starttime='"+runTime+"'>\n")
            fh.write("<title>"+iartist+" : "+ititle+" : "+ialbum+"</title>\n")
            if(self.withArtwork==True and not iart==[]):
                runTimeA=string.replace(str(runTimeA), '.', '')
                theArtString="<picture>art/%s.%s</picture>\n" % (runTimeA, theArtFormat)
                fh.write(theArtString)
            else:
                fh.write("<picture></picture>\n") #consider having a default image
            #fh.write("<link>"+iprofit+"</link>\n")
            fh.write("</chapter>\n")
            fh.close()
            
            #write the artwork to disc
            if(self.withArtwork==True and not iart==[]):
                if not os.path.exists(self.m4bFolderPath+"/art"):os.mkdir(self.m4bFolderPath+"/art")
                theArtPath="%s/art/%s.%s" % (self.m4bFolderPath, runTimeA, theArtFormat)
                fa = open(theArtPath, 'wb')
                fa.write(theArt)
                fa.close()
                
