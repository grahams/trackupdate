"""Live engine: polls Swinsian, dispatches to live plugins, serves commands.

Every poll tick and client command runs serially on the thread that calls
`run`. Each plugin call, listener call and command is isolated so a single
failure can never stop track logging.
"""
import argparse
import configparser
import logging
import os
import queue
import signal
import sqlite3
import sys
import threading
import time
from dataclasses import replace
from datetime import date, datetime

import archive
import db_schema
import engine_server
import episode_db
import plugin_loader
import runtime
import track_source
from session import Session
from Track import Track

logger = logging.getLogger("engine")

POLL_FAILED = "Swinsian poll failed (see engine.log)"
LOCKED_PLUGIN = "SqliteTarget"


def _fmt_time(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f") if dt else None


class Engine:
    def __init__(self, *, config, episode, plugin_classes,
                 poller=track_source.poll_swinsian,
                 artwork=track_source.search_artwork,
                 connect=None, now=datetime.now):
        self.config = config
        self.episode = episode
        self.plugin_classes = list(plugin_classes)
        self._poller = poller
        self._artwork = artwork
        self._now = now
        if connect is None:
            db_path = os.path.expanduser(
                config.get("SqliteTarget", "dbPath", fallback=""))
            connect = lambda: sqlite3.connect(db_path)  # noqa: E731
        self._connect = connect

        get = lambda key, fallback="": config.get(  # noqa: E731
            "trackupdate", key, fallback=fallback)
        self.intro_album = get("introAlbum") or None
        self.ignore_album = get("ignoreAlbum") or None
        self.cover_base_url = get("coverImageBaseURL")
        self.stop_artwork = get("stopArtwork") or date.today().strftime("%Y%m%d.jpg")
        if get("useStopValues") == "True":
            self.stop_track = Track(get("stopTitle"), get("stopArtist"),
                                    get("stopAlbum"), "9:99", None, "", False)
        else:
            self.stop_track = None

        self.session = None
        self.conn = None
        # name -> {"cls", "instance", "enabled"}, in plugin_classes order
        self.plugins = {}
        self.phase = "live"
        self.current_rowid = None
        self.last_error = None
        self.results = []
        self._started = False
        self._queue = queue.Queue()
        self._listeners = []
        self._listeners_lock = threading.Lock()

    # ---- lifecycle -------------------------------------------------------

    def start(self):
        self._started = True
        self.conn = self._connect()
        db_schema.ensure_schema(self.conn)

        last = episode_db.last_row(self.conn, self.episode)
        current = override = last_report = None
        if last is not None:
            current = episode_db.row_to_track(last)
            self.current_rowid = last["rowid"]
            loaded = runtime.load_override()
            if loaded is not None and loaded[0].track.uniqueId == last["uniqueId"]:
                override, last_report = loaded
            else:
                runtime.clear_override()
        else:
            runtime.clear_override()

        self.session = Session(
            ignore_album=self.ignore_album, intro_album=self.intro_album,
            stop_track=self.stop_track, current=current, override=override,
            started=last is not None or override is not None,
            last_report=last_report)
        if override is not None:
            self.session.source = "override"
        elif current is not None:
            self.session.source = "stop" if self._is_stop(current) else "swinsian"

        for cls in self.plugin_classes:
            entry = {"cls": cls, "instance": None, "enabled": True}
            self.plugins[cls.__name__] = entry
            if plugin_loader.is_live(cls):
                self._construct(entry)

    def _is_stop(self, track):
        st = self.stop_track
        return st is not None and (track.title, track.artist, track.album) == (
            st.title, st.artist, st.album)

    def _construct(self, entry):
        name = entry["cls"].__name__
        try:
            entry["instance"] = entry["cls"](self.config, self.episode, None)
            entry["enabled"] = True
            if self.last_error and self.last_error.startswith(f"{name}: failed to start"):
                self.last_error = None
            return True
        except Exception as e:
            logger.exception("%s: failed to start", name)
            entry["instance"] = None
            entry["enabled"] = False
            self.last_error = f"{name}: failed to start: {e}"
            return False

    def run(self, poll_time):
        if not self._started:
            self.start()
        next_tick = time.monotonic()
        while self.phase != "ended":
            timeout = next_tick - time.monotonic()
            if timeout <= 0:
                self.tick()
                next_tick = time.monotonic() + poll_time
                continue
            try:
                cmd = self._queue.get(timeout=timeout)
            except queue.Empty:
                continue
            self.handle(cmd)

    def submit(self, cmd):
        self._queue.put(cmd)

    def subscribe(self, fn):
        with self._listeners_lock:
            self._listeners.append(fn)

    def unsubscribe(self, fn):
        with self._listeners_lock:
            if fn in self._listeners:
                self._listeners.remove(fn)

    # ---- polling and dispatch -------------------------------------------

    def tick(self):
        if self.phase != "live":
            return
        before_error = self.last_error
        try:
            report = self._poller()
        except Exception:
            logger.exception("Swinsian poll raised")
            report = None

        dispatched = False
        try:
            if report is None:
                self.last_error = POLL_FAILED
            elif self.last_error == POLL_FAILED:
                self.last_error = None
            before = self._override_key()
            track = self.session.on_poll(report)
            if track is not None:
                self._dispatch(track, self.session.source)
                dispatched = True
            self._sync_override(before)
        except Exception as e:
            logger.exception("tick failed")
            self.last_error = f"tick failed: {e}"

        if dispatched or self.last_error != before_error:
            self._emit()

    def _override_key(self):
        o = self.session.override
        return None if o is None else (o.track.uniqueId, o.swinsian_idle)

    def _sync_override(self, before):
        after = self._override_key()
        if after == before:
            return
        try:
            if after is None:
                runtime.clear_override()
            else:
                runtime.save_override(self.session.override, self.session.last_report)
        except Exception as e:
            logger.exception("override persistence failed")
            self.last_error = f"override persistence failed: {e}"

    def _dispatch(self, track, source):
        if source in ("swinsian", "override"):
            url = None
            try:
                url = self._artwork(track.title, track.artist)
            except Exception:
                logger.exception("artwork lookup raised")
            track.artworkURL = url or f"{self.cover_base_url}/{self.stop_artwork}"

        self._retry_locked_plugin()
        start_time = self._now()
        for entry in self._live_entries():
            self._call_plugin(entry, track, start_time)

        try:
            last = episode_db.last_row(self.conn, self.episode)
            self.current_rowid = last["rowid"] if last else None
        except Exception as e:
            logger.exception("reading last row failed")
            self.last_error = f"reading last row failed: {e}"

    def _retry_locked_plugin(self):
        """SqliteTarget can never be off: rebuild it if it failed to start."""
        entry = self.plugins.get(LOCKED_PLUGIN)
        if entry is not None and entry["instance"] is None:
            self._construct(entry)

    def _live_entries(self, exclude=()):
        entries = [e for e in self.plugins.values()
                   if plugin_loader.is_live(e["cls"]) and e["enabled"]
                   and e["instance"] is not None
                   and e["cls"].__name__ not in exclude]
        return sorted(entries, key=lambda e: e["cls"].priority, reverse=True)

    def _call_plugin(self, entry, track, start_time):
        name = entry["cls"].__name__
        try:
            entry["instance"].logTrack(track, start_time)
        except Exception as e:
            logger.exception("%s: logTrack failed", name)
            self.last_error = f"{name}: {e}"

    # ---- commands --------------------------------------------------------

    def handle(self, cmd):
        try:
            if not isinstance(cmd, dict):
                raise CommandError(f"invalid command: {cmd!r}")
            name = cmd.get("cmd")
            if name == "end_show":
                self.end_show()
                return  # end_show emits its own snapshots
            handler = self._handlers.get(name)
            if handler is None:
                raise CommandError(f"unknown command: {name!r}")
            handler(self, cmd)
        except CommandError as e:
            self.last_error = str(e)
        except Exception as e:
            logger.exception("command %r failed", cmd)
            self.last_error = f"command failed: {e}"
        self._emit()

    def _cmd_hello(self, cmd):
        pass

    def _row(self, cmd):
        rowid = _field(cmd, "rowid", int)
        for row in episode_db.list_rows(self.conn, self.episode):
            if row["rowid"] == rowid:
                return row
        raise CommandError(f"unknown row: {rowid}")

    def _cmd_edit_row(self, cmd):
        row = self._row(cmd)
        title, artist, album = (_field(cmd, k, str) for k in ("title", "artist", "album"))
        episode_db.update_text(self.conn, row["rowid"], title, artist, album)
        if row["rowid"] != self.current_rowid or self.session.current is None:
            return
        old = self.session.current
        new = replace(old, title=title, artist=artist, album=album)
        self.session.current = new
        override = self.session.override
        if override is not None and override.track.uniqueId == old.uniqueId:
            override.track = new
            self._sync_override(before=None)  # forces a save of the new text
        start_time = self._now()
        for entry in self._live_entries(exclude=(LOCKED_PLUGIN,)):
            self._call_plugin(entry, new, start_time)

    def _cmd_toggle_ignore(self, cmd):
        row = self._row(cmd)
        ignore = not row["ignore"]
        episode_db.set_ignore(self.conn, row["rowid"], ignore)
        if row["rowid"] == self.current_rowid and self.session.current is not None:
            self.session.current.ignore = ignore

    def _cmd_set_override(self, cmd):
        title, artist, album, length = (
            _field(cmd, k, str) for k in ("title", "artist", "album", "length"))
        before = self._override_key()
        track = self.session.set_override(title, artist, album, length)
        self._dispatch(track, "override")
        self._sync_override(before)

    def _cmd_cancel_override(self, cmd):
        before = self._override_key()
        self.session.cancel_override()
        self._sync_override(before)

    def _cmd_toggle_plugin(self, cmd):
        name = _field(cmd, "name", str)
        entry = self.plugins.get(name)
        if entry is None:
            raise CommandError(f"unknown plugin: {name}")
        if name == LOCKED_PLUGIN:
            if entry["instance"] is None:
                self._retry_locked_plugin()  # a failed start: toggling retries it
                return
            raise CommandError(f"{LOCKED_PLUGIN} cannot be turned off")
        if entry["enabled"]:
            entry["enabled"] = False
            return
        if not plugin_loader.is_live(entry["cls"]):
            entry["enabled"] = True
            return
        if entry["instance"] is None and not self._construct(entry):
            return
        entry["enabled"] = True
        if self.session.current is not None:
            self._call_plugin(entry, self.session.current, self._now())

    _handlers = {
        "hello": _cmd_hello,
        "edit_row": _cmd_edit_row,
        "toggle_ignore": _cmd_toggle_ignore,
        "set_override": _cmd_set_override,
        "cancel_override": _cmd_cancel_override,
        "toggle_plugin": _cmd_toggle_plugin,
    }

    # ---- end of show -----------------------------------------------------

    def end_show(self):
        if self.phase != "live":
            return self.results
        self.phase = "ending"
        self._emit()
        results = []
        try:
            for entry in self.plugins.values():
                if entry["instance"] is None or not plugin_loader.is_live(entry["cls"]):
                    continue
                name = entry["cls"].__name__
                try:
                    entry["instance"].close()
                except Exception as e:
                    logger.exception("%s: close failed", name)
                    results.append({"plugin": name, "ok": False, "error": str(e)})
                entry["instance"] = None

            file_classes = [e["cls"] for e in self.plugins.values()
                            if not plugin_loader.is_live(e["cls"]) and e["enabled"]]
            try:
                results.extend(archive.generate(
                    self.config, self.episode, file_classes, self.conn))
            except Exception as e:
                logger.exception("archive pass failed")
                results.append({"plugin": "archive", "ok": False, "error": str(e)})
        finally:
            self.results = results
            self.phase = "ended"
            self._emit()
            try:
                runtime.clear_runtime()
            except Exception:
                logger.exception("clearing runtime files failed")
        return results

    # ---- snapshots -------------------------------------------------------

    def snapshot(self):
        cur = self.session.current if self.session else None
        now_playing = None
        if cur is not None:
            now_playing = {"title": cur.title, "artist": cur.artist,
                           "album": cur.album, "length": cur.length,
                           "source": self.session.source}
        return {
            "event": "snapshot",
            "episode": self.episode,
            "phase": self.phase,
            "onAirSince": _fmt_time(episode_db.first_start_time(self.conn, self.episode)),
            "nowPlaying": now_playing,
            "overrideActive": bool(self.session and self.session.override is not None),
            "currentRowid": self.current_rowid,
            "tracks": episode_db.list_rows(self.conn, self.episode),
            "plugins": [{"name": name,
                         "kind": "live" if plugin_loader.is_live(e["cls"]) else "file",
                         "enabled": e["enabled"],
                         "locked": name == LOCKED_PLUGIN}
                        for name, e in self.plugins.items()],
            "lastError": self.last_error,
            "results": self.results,
        }

    def _emit(self):
        try:
            snap = self.snapshot()
        except Exception:
            logger.exception("building snapshot failed")
            return
        with self._listeners_lock:
            listeners = list(self._listeners)
        for fn in listeners:
            try:
                fn(snap)
            except Exception:
                logger.exception("listener failed; dropping it")
                with self._listeners_lock:
                    if fn in self._listeners:
                        self._listeners.remove(fn)


class CommandError(Exception):
    pass


def _field(cmd, key, typ):
    value = cmd.get(key)
    if typ is int and isinstance(value, bool) or not isinstance(value, typ):
        raise CommandError(f"{cmd.get('cmd')}: missing or invalid {key!r}")
    return value


PLAIN_ONLY_PLUGIN = "StdioTarget"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the trackupdate live engine behind its Unix socket.")
    parser.add_argument("-e", "--episode", required=True)
    parser.add_argument("-t", "--polltime", type=int,
                        help="seconds between polls (overrides pollTime)")
    parser.add_argument("-p", "--pattern", default="*.py",
                        help="glob selecting plugin files")
    parser.add_argument("--grabber", default=track_source.GRABBER_PATH)
    parser.add_argument("--plain", action="store_true",
                        help="foreground mode: also print tracks via StdioTarget")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr)

    running = runtime.engine_alive()
    if running is not None:
        print(f"An engine for episode {running.get('episode')} is already running.",
              file=sys.stderr)
        return 1

    config = configparser.ConfigParser()
    config.read(os.path.expanduser("~/.trackupdaterc"))
    poll_time = args.polltime or config.getint("trackupdate", "pollTime", fallback=10)
    plugin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")
    classes = [cls for cls in plugin_loader.discover(config, plugin_dir, args.pattern)
               if args.plain or cls.__name__ != PLAIN_ONLY_PLUGIN]
    grabber = os.path.abspath(args.grabber)

    engine = Engine(config=config, episode=args.episode, plugin_classes=classes,
                    poller=lambda: track_source.poll_swinsian(grabber))

    def request_end(signum, frame):
        logger.info("signal %d: ending the show", signum)
        # queue.Queue isn't reentrant; never put from inside a signal handler.
        threading.Thread(target=engine.submit, args=({"cmd": "end_show"},),
                         daemon=True).start()

    server = engine_server.serve(engine)
    ended = False
    try:
        runtime.write_info(args.episode, os.getpid())
        signal.signal(signal.SIGINT, request_end)
        signal.signal(signal.SIGTERM, request_end)
        logger.info("engine for episode %s running (pid %d, poll %ds)",
                    args.episode, os.getpid(), poll_time)
        engine.run(poll_time)
        ended = True
    finally:
        engine_server.shutdown(server)
        if not ended:
            runtime.clear_stale()  # keep any override for the restarted engine

    for r in engine.results:
        line = f"{r['plugin']}: {'ok' if r.get('ok') else 'FAILED'}"
        if r.get("error"):
            line += f" ({r['error']})"
        logger.info("%s", line)
        if args.plain:
            print(line)
    logger.info("show ended")
    return 0


if __name__ == "__main__":
    sys.exit(main())
