# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`trackupdate` is a macOS radio-show authoring toolchain. The main daemon (`trackupdate.py`) polls a music player every N seconds for the currently playing track and dispatches that track to a list of "target" plugins that each do something with it (write Audio Hijack's `NowPlaying.txt`, append to a CUE sheet, post to Slack, write a Hugo blog post, insert into SQLite, etc.). A SQLite database accumulates the per-episode track history, and a Flask web editor (`web_editor.py`) lets the user visually fix up that history against the recorded audio file.

Despite the historical mentions of iTunes/Apple Music in the README, the live track source is currently **Swinsian**, read via the bundled `util/swinsian-track-grabber` binary (subprocess that returns JSON).

## Running things

```bash
# Live mode — poll Swinsian and dispatch tracks to enabled plugins
./trackupdate.py -e <episode-number> [-v] [-t <pollSeconds>]

# Archive mode — replay an episode's tracks from the sqlite db through plugins
# (only plugins with enableArchive = True will fire; see below)
./trackupdate.py -a -e <episode-number>

# Web editor — Flask app on http://localhost:5042, edits the configured sqlite db
python web_editor.py

# Import an m3u playlist as a synthesized episode (used for canned/pre-recorded shows)
util/m3u_import.py -e <episode-number> -d "<YYYY-MM-DD HH:MM:SS>" -f <path-to-m3u>
```

There are no tests, no linter config, and no build step — it's a script-based project.

The conda env in `environment.yml` is stale (Python 3.10, pinned 2022 packages). Treat it as a hint about dependencies (`requests`, `mutagen`, `mastodon-py`, `tabulate`, `flask` for the editor) rather than a reproducible environment.

## Configuration

Everything is driven by `~/.trackupdaterc` (INI format, see `example-trackupdaterc`). The `[trackupdate]` section configures the daemon itself; every plugin has its own `[<ClassName>]` section keyed on the plugin's class name, and each plugin must set `enabled: True` in its section or it will be skipped at load time.

Key plumbing values: `[SqliteTarget].dbPath` is *also* read directly by `trackupdate.py` (archive mode) and `web_editor.py` to locate the database — it is the canonical DB path even when `SqliteTarget` itself is disabled.

`[trackupdate].pollScriptPath` is vestigial: it's loaded into `self.pollScriptPath` but never used. The live loop hardcodes `subprocess.check_output(["util/swinsian-track-grabber"])`. Don't rely on the config key to swap the track source.

## Plugin architecture

This is the only piece of "big picture" that requires reading multiple files:

- `Target.py` defines the base class. Subclasses set `pluginName`, `priority` (higher = called first; `pluginList` is sorted descending), and `enableArchive` (default `False`; archive mode skips plugins where this is `False`).
- `trackupdate.py:loadPlugins` discovers plugins by `glob`'ing `plugins/<pattern>.py` (pattern overridable with `-p`). For each matching file, **the filename stem, the class name, and the config section name must all be identical** — `loadPlugins` derives the class name from the filename and then does `config.get(className, 'enabled')` and `getattr(mod, className)`.
- Each plugin's `logTrack(track, startTime)` is invoked on every track change. `Track` (see `Track.py`) is a dataclass with `title/artist/album/length/artworkURL/uniqueId/ignore`.
- The `ignore` flag is set automatically when the album matches `[trackupdate].ignoreAlbum` — plugins should respect it (e.g., skip from listings, but still update "now playing" state).
- `processCurrentTrack` does an iTunes Search API lookup to attach `artworkUrl` before dispatch; falls back to `coverImageBaseURL/stopArtwork` (defaults to today's `YYYYMMDD.jpg`).

To add a new target: subclass `Target`, drop it in `plugins/`, ensure filename == classname == config section, and add `enabled: True` to the rc file.

## Database schema

Single table `trackupdate`. The schema lives in `db_schema.py` (`ensure_schema(conn)`) and is imported by `SqliteTarget`, `web_editor`, `util/m3u_import`, and `util/timeshift`. Util scripts add the repo root to `sys.path` at the top so the import works when they're run standalone.

```
episodeNumber INTEGER NOT NULL, uniqueId, title, artist, album,
length, startTime TIMESTAMP, "ignore" INTEGER DEFAULT 0, artworkUrl
```

There is no primary key — the editor identifies rows by `uniqueId` when available, falling back to SQLite's implicit `rowid` (encoded as the string `"rowid_<n>"` over the API). The `"ignore"` column is quoted because it's a SQL reserved word; preserve the quoting in any new SQL.

`startTime` is stored as a space-separated timestamp (`YYYY-MM-DD HH:MM:SS.ffffff`), *not* the ISO `T`-separated form — `web_editor.format_timestamp` exists specifically to enforce this. `datetime.fromisoformat` parses both, but anything that writes new rows must use the space form.

## Web editor specifics

- Frontend is a single `templates/editor.html` + `static/editor.js` + `static/editor.css`, using WaveSurfer.js for the waveform.
- All track positions in the API are expressed as `startTimeSeconds` relative to the first track of the episode; the server converts to/from absolute `startTime` using the earliest row as the anchor.
- Uploaded audio is written to a per-process tempdir (`tempfile.mkdtemp()`) and lost on restart — this is intentional.
- `import_m3u` runs `ffprobe` (via `util/m3u_import.py`) for accurate durations; ffprobe needs to be on PATH.
- **The waveform is never decoded in the browser.** `waveform_peaks.py` shells out to `ffmpeg` to build a min/max envelope (8 kHz mono, 100 peaks/sec, little-endian Float32 interleaved min/max), `/api/audio/<filename>/peaks` serves it as binary, and `editor.js` passes it to `wavesurfer.load(url, [peaks], duration)`. Given peaks *and* a duration, WaveSurfer skips both the blob fetch and `decodeAudioData` entirely — the earlier `backend: 'WebAudio'` path decoded the whole mp3 to ~2.5 GB of PCM, which is what made loading slow. Don't reintroduce a backend override.
  - The ffmpeg call must pass `-vn`: the show mp3s carry embedded artwork, and the mjpeg stream otherwise corrupts the f32 output.
  - Peaks are cached in `<dir of dbPath>/peaks_cache/`, keyed on path + mtime + size, so unlike the upload tempdir they survive a restart. Roughly 5.7 MB per 2-hour show; safe to delete.
  - **ffmpeg (not just ffprobe) is now a dependency.** If it's missing the peaks route returns 501 and the editor falls back to decoding in-browser, so things still work — just slowly.

## Things that are NOT what they look like

- Several plugins named in the README no longer exist. `LadioCastTarget`, `MastodonTarget`, `BlogFileTarget`, and `SlackTarget` were removed (`7a4d91b`); `TwitterTarget` was removed earlier (`4baef1b`); `ListFileTarget` was split apart into `TrackListFileTarget`/`WikiFileTarget`/`CsvFileTarget`/etc. (`e760d74`). Don't restore references to any of them.
- `Automation/*.scpt` are legacy AppleScript track-grabbers; the live code path uses the compiled `util/swinsian-track-grabber` binary instead.
- `util/timeshift.py` is a one-off scratchpad with hardcoded episode numbers and a hardcoded `dbPath` — treat it as throwaway, not a reusable utility.
