#!/usr/bin/python

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

import os
import time
import sys
import getopt
import ConfigParser
import glob
import logging

from appscript import *

class MakeM4B:
    audioIn=""
    audioOut=""
    theXML=""
    theFolder=""
    chapterToolPath="/Applications/GarageBand.app/Contents/MacOS/ChapterTool "

    def usage(self):
        print( "Usage: makeM4B.py -x file.xml -a file.mp3 -o file.m4b" )
        print( "Usage: makeM4B.py -f folder_path" )
        print( """
This script uses afconvert and ChapterTool to turn a mp3 and associated xml file into an "advance mp3" (m4b) file. It is meant to work in conjunction with trackupdate.py

Requires:
    /usr/bin/afconvert
    /Applications/GarageBand/Contents/MacOS/ChapterTool

Arguments:
    -x  --xml         xml file
    -a  --audio.mp3   input mp3 file name
    -o  --audio.m4b   output m4b file name
    -f  --folder      folder containing xml and mp3
    -h  --help        show this help page
    -v  --verbose     you are lonely and want trackupdate to talk more

Examples:
    ./makeM4B.py -x xmlfile.xml -a audiofile.mp3 -o outFile.m4b
    ./makeM4B.py -f folderPath
    """)

    def __init__(self,argv):
        # process command-line arguments
        if(len(argv) > 0):
            try:
                opts, args = getopt.getopt(sys.argv[1:], "x:a:o:f:h:v", ["xml=",
                                                                   "audioin=", "audioout=", "folder=", "help", "verbose"])
            except getopt.GetoptError, err:
                # print help information and exit:
                logging.error(str(err)) # will print something like "option -a not recognized"
                self.usage()
                sys.exit(2)

            for o, a in opts:
                if o in ("-x", "--xml"):
                    self.theXML = a
                elif o in ("-a", "--audioin"):
                    self.audioIn = a
                elif o in ("-o", "--audioout"):
                    self.audioOut = a
                elif o in ("-f", "--folder"):
                    self.theFolder = a
                elif o in ("-v", "--verbose"):
                    # remove any logging handlers created by logging before
                    # BasicConfig() is called
                    root = logging.getLogger()
                    if root.handlers:
                        for handler in root.handlers:
                            root.removeHandler(handler)

                    logging.basicConfig(level=logging.DEBUG)
                    logging.debug("Starting up.")
                elif o in ("-h", "--help"):
                    self.usage()
                    sys.exit()
                else:
                    assert False, "unhandled option"
            #-x, -a and -o must ALL be present if one is
            if (self.theFolder==""):
                if(self.theXML=="" or self.audioIn=="" or self.audioOut==""):
                    print("***xml file, mp3 file and output name for m4b file must be specified.***")
                    self.usage()
                    sys.exit()
        else:
            self.usage()
            sys.exit()
        self.makeTheFile()
                    
    def makeTheFile(self):
        #make sure the files/folder are real.
        #is folder real
        if(not self.theFolder==""):
            if(os.path.exists(self.theFolder)):
                #folder exists. Do the files exist
                self.theXML = glob.glob(self.theFolder+"/*.xml")
                if(len(self.theXML)>0):
                    self.theXML=self.theXML[0]
                else: 
                    print("***XML file not found. Please use the -h option to see parameters.***")
                    sys.exit()
                self.audioIn = glob.glob(self.theFolder+"/*.mp3")[0]
                if(len(self.audioIn) > 0):
                    theName=os.path.split(self.audioIn)[1]
                    theName=os.path.splitext(theName)[0]
                    self.audioOut=self.theFolder+"/"+theName
        #now that the necessary paths are filled in, check and make sure they actualy exist
        if(not os.path.exists(self.theXML)):
                print("***XML file not found. Please use the -h option to see parameters.***")
                sys.exit()      
        if(not os.path.exists(self.audioIn)):
                print("***Audio file (mp3) not found. Please use the -h option to see parameters.***")
                sys.exit()
        self.audioOut=os.path.splitext(self.audioIn)[0]
        if(self.theFolder==""):
            self.theFolder=os.path.split(self.audioIn)[0]
            
        print("Making a copy of the archive as an m4a...")
        theCommand="afconvert -f 'mp4f' -d 'aac ' '%s' '%s.m4a'" % (self.audioIn, self.audioOut)
        os.system(theCommand)
        #check and see if the m4a was made
        if(not os.path.exists(self.audioOut+".m4a")):
            print("***Audio file (m4a) not found. Please use the -h option to see parameters.***")
            sys.exit()
        self.audioIn=self.audioOut+".m4a"
        
        print("Making m4b file...")
        currWorkDir=os.getcwd()
        os.chdir(self.theFolder)
        theCommand="%s -x '%s' -a '%s' -o '%s.m4b'" % (self.chapterToolPath, self.theXML, self.audioIn, self.audioOut)
        os.system(theCommand)
        os.chdir(currWorkDir)

if __name__ == "__main__":
    makeM4B = MakeM4B(sys.argv[1:])
