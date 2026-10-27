#!/usr/bin/env -S uv run

# Copyright (c) 2009-2014 Sean M. Graham <www.sean-graham.com>
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
import sys
import getopt
import configparser
import logging
import plugin_loader
import archive
import sqlite3

import launcher

REPO = os.path.dirname(os.path.abspath(__file__))
TUI_CRASHED = ("The TUI stopped unexpectedly. The engine for episode {episode} "
               "is still running and logging tracks; re-run the same command "
               "to reattach.")


class TrackUpdate(object):
    episodeNumber = "XX"
    useDatabase = False
    plain = False
    verbose = False
    pollTime = None
    pluginPattern = None
    grabber = None
    dbPath = None
    conn = None
    c = None
    logger = logging.getLogger()

    def usage(self):
        print( "Usage: trackupdate.py [arguments]" )
        print( """
Polls Swinsian for the currently playing track and hands it to the target
plugins (Audio Hijack's NowPlaying.txt, the sqlite db, ...). By default this
starts the live engine in the background, or attaches to the one already
running for the episode, and opens the TUI. Closing the TUI leaves the
engine running; re-run the same command to reattach. End the show from the
TUI (Ctrl-C, then "End show") to write the CUE/list/wiki/CSV files.

Arguments:
    -e  --episode     the episode number (required)
    -t  --polltime    seconds between polls (overrides pollTime; new engine only)
    -p  --pattern     plugin filename pattern (defaults to '*.py'; new engine only)
    -v  --verbose     verbose engine logging
        --plain       no TUI: run the engine in the foreground, printing
                      tracks to the terminal; Ctrl-C ends the show
    -a  --archive     use the sqlite db as the track source
    -h  --help        show this help page

Example:
    ./trackupdate.py -e 42
    ./trackupdate.py -e 42 --plain -v
    ./trackupdate.py -a -e 42
    """)

    def __init__(self,argv):
        self.logger.setLevel(logging.WARNING)

        try:
            opts, args = getopt.getopt(argv, "he:t:p:va", ["help",
                                       "episode=", "polltime=",
                                       "pattern=", "verbose", "archive",
                                       "plain", "grabber="])
        except (getopt.GetoptError) as err:
            # print help information and exit:
            self.logger.error(str(err)) # will print something like
                                   # "option -a not recognized"
            self.usage()
            sys.exit(2)

        for o, a in opts:
            if o in ("-e", "--episode"):
                self.episodeNumber = a
            elif o in ("-a", "--archive"):
                self.useDatabase = True
            elif o in ("-t", "--polltime"):
                self.pollTime = max(1, int(a))
            elif o in ("-p", "--pattern"):
                self.pluginPattern = a
            elif o in ("-v", "--verbose"):
                self.verbose = True
            elif o == "--plain":
                self.plain = True
            elif o == "--grabber":  # hidden: a stand-in grabber for testing
                self.grabber = os.path.abspath(a)
            elif o in ("-h", "--help"):
                self.usage()
                sys.exit()
            else:
                assert False, "unhandled option"

        try:
            if(self.useDatabase):
                self.archiveMode()
            else:
                self.liveMode()
        except KeyboardInterrupt:
            pass

    def archiveMode(self):
        if(self.verbose):
            # remove any logging handlers created by logging before
            # BasicConfig() is called
            if(self.logger.handlers):
                for handler in self.logger.handlers:
                    self.logger.removeHandler(handler)

            self.logger.setLevel(logging.DEBUG)
            logging.debug("Starting up. Press Ctrl-C to stop.")

        # process config file
        if not os.path.isfile(os.path.expanduser('~/.trackupdaterc')):
            self.logger.warning("Warning: no config .trackupdaterc file.")

        config = configparser.ConfigParser()
        config.read(os.path.expanduser('~/.trackupdaterc'))

        try:
            for key in ('introAlbum', 'pollTime', 'useStopValues', 'stopTitle',
                        'stopArtist', 'stopAlbum', 'stopArtwork', 'ignoreAlbum',
                        'coverImagePath', 'coverImageBaseURL', 'pollScriptPath'):
                config.get('trackupdate', key)
            self.dbPath = config.get('SqliteTarget', 'dbPath')
        except configparser.NoSectionError:
            self.logger.error("Warning: Invalid config file, no [trackupdate] section.")
            pass
        except configparser.NoOptionError:
            self.logger.error("[trackupdate]: Missing values in config")
            return

        self.logger.debug("In archive mode, reading from sqlite db")
        self.logger.debug("Episode #: %s" % str(self.episodeNumber))

        if(self.episodeNumber == "XX"):
            self.logger.error('Episode number ("-e/--episode") required for archive mode')
        else:
            self.dbPath = os.path.expanduser(self.dbPath)
            self.conn = sqlite3.connect(self.dbPath)
            self.c = self.conn.cursor()

            self.archiveLoop(config)

    def archiveLoop(self, config):
        classes = plugin_loader.discover(config, REPO + "/plugins/",
                                         self.pluginPattern or "*.py")
        results = archive.generate(config, self.episodeNumber, classes, self.conn)
        for r in results:
            if not r["ok"]:
                self.logger.error("%s: archive failed: %s" % (r["plugin"], r["error"]))

    def engineArgs(self):
        args = []
        if(self.grabber):
            args += ["--grabber", self.grabber]
        if(self.pollTime is not None):
            args += ["-t", str(self.pollTime)]
        if(self.pluginPattern):
            args += ["-p", self.pluginPattern]
        if(self.verbose):
            args.append("-v")
        return args

    def liveMode(self):
        if(self.episodeNumber == "XX"):
            print('Episode number ("-e/--episode") required', file=sys.stderr)
            self.usage()
            sys.exit(2)

        if(self.plain):
            # Replace this process so Ctrl-C goes straight to the engine.
            os.execv(sys.executable, [sys.executable, launcher.ENGINE_SCRIPT,
                                      "-e", self.episodeNumber, "--plain"]
                     + self.engineArgs())

        # Load the TUI before starting anything, so a missing textual can't
        # leave a detached engine running with no way to attach to it.
        try:
            import tui  # only live mode needs textual
        except ImportError as e:
            print(f"Can't load the TUI ({e}). Install textual, or run with "
                  "--plain.", file=sys.stderr)
            sys.exit(1)

        try:
            started = launcher.ensure_engine(
                self.episodeNumber, grabber=self.grabber,
                poll_time=self.pollTime, pattern=self.pluginPattern,
                verbose=self.verbose)
        except launcher.EngineBusy as e:
            print(f"An engine for episode {e.episode} is already running; "
                  "end that show first.", file=sys.stderr)
            sys.exit(1)
        except launcher.EngineStartFailed as e:
            print(f"Could not start the engine: {e}", file=sys.stderr)
            sys.exit(1)

        if(not started and (self.pollTime is not None or self.pluginPattern)):
            print("Attached to the running engine; its poll time and plugin "
                  "pattern are kept.", file=sys.stderr)

        try:
            app = tui.TrackUpdateApp(tui.EngineLink())
            app.run()
            code = app.return_code or 0
        except Exception as e:
            print(f"{type(e).__name__}: {e}", file=sys.stderr)
            code = 1
        if(code != 0):
            print(TUI_CRASHED.format(episode=self.episodeNumber), file=sys.stderr)
            sys.exit(code)

if __name__ == "__main__":
    trackUpdate = TrackUpdate(sys.argv[1:])
