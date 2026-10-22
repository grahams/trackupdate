# Live TUI for trackupdate — design

Date: 2026-10-21
Status: draft, awaiting approval

## Why

Today, live mode (`./trackupdate.py -e <n>`) polls Swinsian and echoes each
track to stdout. That's all the feedback there is during a show, and there's no
way to act on what you see. Three needs come up in practice:

1. **See the show so far**: a scrollable list of every track played this
   episode, when it started, and how long it is.
2. **Fix small typos while on air**: wrong title, artist, or album in the db.
3. **Override the current track** when Swinsian is wrong or isn't the source:
   vinyl, a live guest, a file with bad tags. The user has had to "resort to
   hacks" for this in the past. It doesn't happen often, but when it does the
   correct details should go everywhere, as though Swinsian had reported them.

A fourth, smaller need: **enable/disable plugins for this session only**.

The user also realised during design that the per-file artifacts (CUE sheet,
track list, wiki, CSVs, Hugo post) don't need to be written live. The db holds
everything, and archive mode can already rebuild them from it. Generating them
once at the end of the show means typo fixes made during the show automatically
reach every file, and it removes a hazard that exists today: the file plugins
open their outputs with `'w'` (e.g. `plugins/CueFileTarget.py:77`), so
restarting the daemon mid-show truncates them.

## Goals

- The TUI is the **default** for live mode. `./trackupdate.py -e 412` opens it.
- A crash or bug in the TUI **must never stop track logging**. (The user's
  stated top concern: "if the TUI crashes and stops logging tracks mid-show".)
- Only two things happen live: the SQLite insert and Audio Hijack's
  `NowPlaying.txt`. Everything else is generated at end of show.
- Typo edits, overrides, and plugin toggles can all be done from the TUI
  without restarting anything.

## Non-goals

- Editing start times, waveform alignment, or audio work. That's what
  `web_editor.py` is for, and it stays as is.
- Persisting plugin toggles back to `~/.trackupdaterc`. Toggles are
  session-only.
- Changing archive mode (`-a`). It stays a plain, run-once command with plain
  output. It's also the recovery path if a show ends without the files being
  generated.
- Running more than one episode at once, or remote access to the engine.

## Anti-goals (failure even if it "works")

- Any path where a UI exception, a closed terminal window, or a hung redraw
  stops the polling or the db insert.
- Anything that truncates, overwrites, or loses data mid-show, including on an
  engine restart.
- Reintroducing live writes of the file artifacts.
- An accidental Ctrl-C ending the show.

## Architecture (decided)

**Two processes.** The user chose this explicitly over a single process.

### Engine

A background process that does the work `TrackUpdate.liveLoop` does today:

- Polls `util/swinsian-track-grabber` every `pollTime` seconds, including the
  existing intro-album wait and stop-values behaviour.
- Does the iTunes artwork lookup and builds the `Track` (current
  `processCurrentTrack` logic, `ignoreAlbum` handling included).
- Dispatches each track change to the **live plugins** only: the enabled
  plugins with `enableArchive = False`. Today those are `SqliteTarget` and
  `AudioHijackTarget` (and `StdioTarget`, see plain mode below).
- Holds the session state: the current track, any active override, and which
  plugins are toggled on.
- Accepts commands from the TUI (edit row, set override, toggle plugin, end
  show) and pushes state changes to it (new track, override started/ended, row
  edited, errors).
- Keeps running when the TUI disconnects for any reason.
- On **end show**: stops polling, closes the live plugins (AudioHijack's
  `close()` removes `NowPlaying.txt`, as today), then runs an archive pass. It
  reads the episode's rows from the db in `startTime` order and feeds them
  through the enabled file plugins (`enableArchive = True`), exactly as
  `archiveLoop` does today, then closes them. It reports which files were
  written, then exits.

**Resuming.** If the engine dies and is restarted for the same episode, it
must
not create a duplicate row for the track that's already playing. Seed "current
track" from the episode's most recent db row before the first poll. Because no
files are written until end of show, a restart can't truncate anything.

### TUI

A separate process, built with **Textual** (my call; the user didn't object).
It connects to the engine and is purely a view and controller. It holds no
state the engine doesn't have. If it crashes, the user re-runs the same command
and it reconnects, and history comes back from the db.

### Launch behaviour

- `./trackupdate.py -e 412`: if no engine is running, start one (detached, so
  it survives the TUI exiting and the terminal window closing), then open the
  TUI attached to it. If an engine for episode 412 is already running, just
  attach.
- If an engine for a *different* episode is running, refuse with a clear
  message. Don't start a second engine or attach to the wrong one.
- A flag (e.g. `--plain`) gives the old behaviour: engine in the foreground,
  `StdioTarget` printing tracks, no TUI. In plain mode, Ctrl-C ends the show,
  which now means generating the files at the end.
- `-a` archive mode: unchanged.

## TUI layout (decided: tabs)

The user picked the tabbed layout from the mockups.

- **Header:** app name, episode number, time on air.
- **Now playing card**, always visible above the tabs: title, artist, album,
  length, and the source (`Swinsian` or `OVERRIDE`). An active override is
  visually distinct (the mockup used orange plus an "until Swinsian changes"
  note).
- **Tracks tab:** scrollable table of every row for this episode: #, start time
  (wall clock), length, title, artist. Ignored rows (`ignore = 1`) are dimmed.
  The current track is highlighted. It follows new tracks as they arrive
  unless the user has scrolled up.
- **Plugins tab:** one line per plugin found in `plugins/` that's enabled in the
  rc file, grouped as *Live* and *Generated at end of show*, each with an
  on/off toggle.
- **Footer:** key hints.

## Behaviours

### Fixing typos (Tracks tab)

- Select a row and edit **title, artist, album** in a small form. Saving
  updates that row in the db. Rows are identified as the web editor does it:
  `uniqueId` when present, else `rowid`.
- Editing the **currently playing** row also rewrites `NowPlaying.txt` (my
  call). Push the corrected track to `AudioHijackTarget` only. Don't re-dispatch
  to all live plugins, because `SqliteTarget.logTrack` inserts a new row.
- Edits change text only; they don't re-run the artwork lookup or replace the
  cached cover (my call; artwork fixes stay a post-show job).
- A key toggles a row's `ignore` flag (user confirmed). The row's dimming
  updates right away, and the end-of-show files respect the new value.
- Start times are not editable here (non-goal).

### Override

- A key opens a form: title, artist, album, length. Submitting dispatches that
  track to the live plugins right away, as a normal track change: a new db row
  with `startTime = now`, and `NowPlaying.txt` updated. Artwork goes through the
  same iTunes lookup and default-cover fallback as a Swinsian track.
- The override **ends when Swinsian starts playing again** (user's decision,
  refined). The user's real workflow is to set the override, mute Swinsian at
  first, then pause it until they're ready to go back to it. So:
  - Swinsian pausing or stopping while an override is active is **neutral**.
    The override stays. Stop values are *not* logged or pushed to
    `NowPlaying.txt` during an override.
  - The override ends when Swinsian goes from paused/stopped back to playing.
    That newly playing track is then logged as usual, even if it's the same
    track that was paused.
  - A track change while Swinsian is still playing muted does **not** end the
    override (my call). Otherwise a muted playlist advancing on its own would
    put the wrong track on air over the vinyl. The cost is that if the user
    never pauses, they press the cancel key to end the override.
  - **Builder must verify first:** what `util/swinsian-track-grabber` outputs
    when Swinsian is paused vs stopped vs playing. The rule above needs a
    play state. If the grabber can't tell paused from playing, extend it (or
    query Swinsian's player state another way) before building the override.
- Override tracks get a UUID as their `uniqueId` (user's decision). `Track.fetchArtwork` names the cover file
  `<uniqueId>.jpg`, so an empty id would make every override share `.jpg`. A
  unique id also keeps the row addressable by the web editor.
- A key cancels an active override early (user confirmed). Cancelling doesn't log
  anything new; it just goes back to following Swinsian on the next change.
- An active override **survives an engine restart** (my call, from the
  anti-goal about restarts). The engine persists the active override and the
  grabber output it's comparing against to a small state file. On resume it
  restores that, so the first poll doesn't log Swinsian's track over the vinyl.
  The file is cleared when the override ends.

### Plugin toggles (Plugins tab)

- Session-only. Never written to the rc file.
- Turning a **live** plugin off means it stops receiving tracks. Turning it back
  on pushes the current track to it right away (so `NowPlaying.txt` catches up).
- Turning a **file** plugin off means it's skipped at end of show.
- `SqliteTarget` cannot be turned off (my call). The whole design relies on the
  db being complete; show it as locked on.

### Ending the show and quitting

My call, because Ctrl-C is the user's habit at end of show and the TUI and
engine are now separate:

- **Ctrl-C or `q`** opens a prompt with three choices:
  - **End show**: the engine stops polling and generates the files. The TUI
    shows progress and a summary of the files written, then both exit.
  - **Close window**: the TUI exits and the engine keeps logging. Re-run the
    command to reattach.
  - **Cancel**: back to the TUI.
- The default focus is not "End show". One stray keypress mustn't end a show.

### Errors

Today errors go to the logger or stdout (`swinsian-track-grabber timed out`,
artwork search failures, plugin exceptions). The engine should write them to a
log file. The TUI should show the latest one unobtrusively (e.g. a line in the
header or footer) without stealing focus (my call). A failing plugin must not
stop other plugins, as today.

## Constraints

- Follow the CLAUDE.md conventions: plugin filename == class name == config
  section; `[SqliteTarget].dbPath` is the canonical db path; preserve the
  quoting of `"ignore"`; any new rows use the space-separated `startTime` form.
- The web editor is never used during a show (user confirmed). There's no need
  to handle concurrent edits from it. The engine and TUI still share the db, so
  keep transactions short.
- New dependency: `textual`. Mention it alongside the others; `environment.yml`
  is stale anyway.
- No tests or linter exist. Don't add a framework as part of this unless it's
  needed.

## Left to the builder

- The engine↔TUI transport (e.g. a Unix domain socket in a known location,
  newline-delimited JSON) and how the TUI discovers a running engine and its
  episode number.
- How the engine is detached and how a stale socket or pid from a crashed
  engine is detected.
- How `trackupdate.py` is split into engine and TUI modules, and how much of the
  existing `TrackUpdate` class is reused versus refactored.
- Key bindings beyond Ctrl-C / `q`, and visual styling.
- Where the engine log file lives.
