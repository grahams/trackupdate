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
import json
import urllib2

from appscript import *

from subprocess import *

class XMLTarget(Target):
    theFileName = ""
    pluginName = "XML for Advanced Podcasts"
    m4bFolderPath = ""
    mp3FilePath = ""
    chapterToolPath = ""
    withArtwork = "True"
    defaultArt= ""
    withLinks = "True"
    linkUrl = ""
    queryUrl = ""
    runTime = ""
    startTime = -1


    def __init__(self, config, episode):
        try:
            self.m4bFolderPath = config.get('XMLTarget', 'm4bFolder')
            self.mp3FilePath = config.get('XMLTarget', 'mp3FilePath')
            self.chapterToolPath = config.get('XMLTarget', 'chapterToolPath')
            self.withArtwork = config.get('XMLTarget', 'includeArt')
            self.defaultArtwork = config.get('XMLTarget', 'defaultArt')
            self.withLinks = config.get('XMLTarget', 'includeLinks')
            self.linkUrl = config.get('XMLTarget', 'linkUrl')
            self.queryUrl = config.get('XMLTarget', 'queryUrl')
        except ConfigParser.NoSectionError:
            print("%s: No [MakeM4B] section in config") % (self.pluginName)
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
        
        #make a symlink from the folder with xml to the mp3 to use
        fileDate = time.localtime(self.startTime)
        fileDate = time.strftime("%Y%m%d",fileDate)
        self.mp3FilePath=os.path.expanduser(self.mp3FilePath)
        theMP3File = glob.glob(self.mp3FilePath+"Nicecast Archived Audio "+fileDate+"*.mp3")
        if(len(theMP3File) > 0):
            theMP3File=theMP3File[-1]
            os.symlink(theMP3File, self.m4bFolderPath+"/target_mp3.mp3")


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
            ##Include Artwork##
            if(self.withArtwork=="True"):
                if(not iart==[]):
                    runTimeA=string.replace(str(runTimeA), '.', '')
                    theArtString="<picture>art/%s.%s</picture>\n" % (runTimeA, theArtFormat)
                    fh.write(theArtString)
                elif(iart==[] and os.path.exists(self.defaultArtwork)==True):
                    defaultArtNm=os.path.basename(self.defaultArtwork)
                    fh.write("<picture>art/"+defaultArtNm+"</picture>\n")
                else:
                    fh.write("<picture></picture>\n")
            ##Include Links##
            ##I'm not 100% happy with this. Feels cludgy
            ##This can also result in lag if unable to get a reply from network
            if(self.withLinks=="True"):
                theAlbum=ialbum
                theUrl=""
                for i in range(2):
                    theQuery=self.queryUrl % (iartist, ititle, theAlbum)
                    #try:
                    theResponse=urllib2.urlopen(self.linkUrl,theQuery)
                    theResult = theResponse.read()
                    theResult = theResult.replace('\n', '')
                    theResultDict=json.loads(theResult) #this converts the json into a python dict
                    if theResultDict['resultCount']==1:
                        theResult=theResultDict['results'][0]
                        if theResult['artistName']==iartist or theResult['artistName'].lower()==iartist.lower:
                            if(theResult['trackName']==ititle or theResult['collectionCensoredName']==ititle or theResult['trackName'].lower()==ititle.lower() or theResult['collectionCensoredName'].lower()==ititle.lower()):
                                if(not theAlbum==""):
                                    if(theResult['collectionName']==ialbum or theResult['collectionCensoredName']==ialbum) :
                                        theUrl=theResult['trackViewUrl']
                                        break
                                    else:
                                        theAlbum=""
                                else:
                                    theUrl=theResult['trackViewUrl']
                                    break
                    else:
                        theAlbum=""
                    #except:
                    #    break
                #fh.write("<link>"+theUrl+"</link>\n")
                fh.write('<link href="'+theUrl+'">Buy Track</link>\n')
    
            fh.write("</chapter>\n")
            fh.close()
            
            #write the artwork to disc
            if(self.withArtwork=="True"):
                if not os.path.exists(self.m4bFolderPath+"/art"):os.mkdir(self.m4bFolderPath+"/art")
                if(iart==[] and os.path.exists(self.defaultArtwork)==True):
                    #don't copy the file if it exists
                    defaultArtNm=os.path.basename(self.defaultArtwork)
                    if(os.path.exists(self.m4bFolderPath+"/art/"+defaultArtNm)==False):
                        shutil.copy(self.defaultArtwork, self.m4bFolderPath+"/art/"+defaultArtNm)
                elif(not iart==[]):
                    theArtPath="%s/art/%s.%s" % (self.m4bFolderPath, runTimeA, theArtFormat)
                    fa = open(theArtPath, 'wb')
                    fa.write(theArt)
                    fa.close()
                
