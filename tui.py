"""Textual client for a running engine: renders its snapshots, sends commands.

The TUI holds no state of its own. Everything on screen comes from the
latest engine snapshot; user actions are sent as commands and the display
changes only when the engine's next snapshot says so.
"""
import asyncio
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widgets import (Button, DataTable, Footer, Input, Label, Static,
                             Switch, TabbedContent, TabPane)

import runtime

CONNECTED = "connected"
DISCONNECTED = "disconnected — retrying"
READ_LIMIT = 16 * 1024 * 1024  # a snapshot carries every row of the episode


class EngineLink:
    """NDJSON connection to the engine socket that reconnects forever.

    Iterating yields engine messages plus `{"event": "link", "status": ...}`
    items whenever the connection comes up or goes down. It never raises
    for connection problems; it waits `retry_delay` seconds and retries.
    """

    def __init__(self, path=None, retry_delay=1.0):
        self.path = Path(path) if path is not None else runtime.socket_path()
        self.retry_delay = retry_delay
        self._reader = None
        self._writer = None

    async def connect(self):
        await self._close()
        self._reader, self._writer = await asyncio.open_unix_connection(
            str(self.path), limit=READ_LIMIT)
        await self.send({"cmd": "hello"})

    async def send(self, cmd: dict):
        if self._writer is None:
            raise ConnectionError("not connected to the engine")
        self._writer.write(runtime.encode(cmd))
        await self._writer.drain()

    async def _close(self):
        writer, self._reader, self._writer = self._writer, None, None
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def __aiter__(self):
        try:
            while True:
                try:
                    await self.connect()
                    yield {"event": "link", "status": CONNECTED}
                    while True:
                        line = await self._reader.readline()
                        if not line:
                            break
                        if not line.strip():
                            continue
                        try:
                            msg = runtime.decode(line)
                        except ValueError:
                            continue
                        yield msg
                except Exception:
                    pass  # refused, reset, oversized line: all mean "retry"
                await self._close()
                yield {"event": "link", "status": DISCONNECTED}
                await asyncio.sleep(self.retry_delay)
        finally:
            await self._close()


def format_header(episode, on_air_since, now: datetime) -> str:
    head = f"trackupdate · Episode {episode}"
    if not on_air_since:
        return f"{head} · not on air yet"
    try:
        since = datetime.fromisoformat(on_air_since)
        secs = max(0, int((now - since).total_seconds()))
    except (ValueError, TypeError):
        return head  # an unexpected value must never break the clock
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{head} · on air {h:02d}:{m:02d}:{s:02d}"


class TrackForm(ModalScreen):
    """A small form of text fields; dismisses with a dict of values or None."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, heading: str, fields: list[tuple[str, str, str]]):
        super().__init__()
        self.heading = heading
        self.fields = fields  # (key, label, initial value)

    def compose(self) -> ComposeResult:
        with Vertical(id="form"):
            yield Label(self.heading, id="form-heading")
            for key, label, value in self.fields:
                yield Label(label)
                yield Input(value=value, id=key)
            with Horizontal(id="form-buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", id="cancel")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "save":
            self._submit()
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _submit(self) -> None:
        values = {key: self.query_one(f"#{key}", Input).value.strip()
                  for key, _, _ in self.fields}
        if not values["title"]:
            self.query_one("#title", Input).focus()
            return
        self.dismiss(values)


class PluginSwitch(Switch):
    """A switch that asks the engine to toggle instead of flipping itself."""

    BINDINGS = [
        Binding("up", "app.focus_previous", show=False),
        Binding("down", "app.focus_next", show=False),
    ]

    class Toggle(Message):
        def __init__(self, name: str):
            super().__init__()
            self.plugin = name

    async def _on_click(self, event) -> None:
        event.stop()
        self.action_toggle_switch()

    def action_toggle_switch(self) -> None:
        self.post_message(self.Toggle(self.name))


class MainScreen(Screen):
    BINDINGS = [
        Binding("e", "edit_row", "Edit row"),
        Binding("i", "toggle_ignore", "Ignore"),
        Binding("o", "override", "Override"),
        Binding("x", "cancel_override", "End override"),
        Binding("tab", "switch_tab", "Tracks/Plugins"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("trackupdate · connecting…", id="header")
        with Vertical(id="now-playing"):
            with Horizontal(classes="np-line"):
                yield Static("Nothing playing", id="np-title")
                yield Static("", id="np-length")
            with Horizontal(classes="np-line"):
                yield Static("", id="np-album")
                yield Static("", id="np-source")
        with TabbedContent(id="tabs"):
            with TabPane("Tracks", id="tracks-tab"):
                yield DataTable(id="tracks", cursor_type="row", zebra_stripes=False)
            with TabPane("Plugins", id="plugins-tab"):
                yield VerticalScroll(id="plugins")
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#now-playing").border_title = "Now playing"
        self.query_one(DataTable).add_columns("#", "Started", "Len", "Title", "Artist")

    def check_action(self, action, parameters):
        if action == "cancel_override":
            return bool(self.app.snap.get("overrideActive"))
        if action in ("edit_row", "toggle_ignore"):
            return self.query_one(TabbedContent).active == "tracks-tab"
        return True

    # ---- actions ---------------------------------------------------------

    def _selected_row(self) -> dict | None:
        table = self.query_one(DataTable)
        if table.row_count == 0:
            return None
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        return self.app.rows.get(int(key))

    def action_edit_row(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        rowid = row["rowid"]

        def done(values):
            if values is not None:
                self.app.send({"cmd": "edit_row", "rowid": rowid, **values})

        self.app.push_screen(TrackForm(f"Edit row {self._row_number(rowid)}", [
            ("title", "Title", row["title"] or ""),
            ("artist", "Artist", row["artist"] or ""),
            ("album", "Album", row["album"] or ""),
        ]), done)

    def _row_number(self, rowid) -> int:
        return self.query_one(DataTable).get_row_index(str(rowid)) + 1

    def action_toggle_ignore(self) -> None:
        row = self._selected_row()
        if row is not None:
            self.app.send({"cmd": "toggle_ignore", "rowid": row["rowid"]})

    def action_override(self) -> None:
        def done(values):
            if values is not None:
                self.app.send({"cmd": "set_override", **values})

        self.app.push_screen(TrackForm("Override now playing", [
            ("title", "Title", ""), ("artist", "Artist", ""),
            ("album", "Album", ""), ("length", "Length", ""),
        ]), done)

    def action_cancel_override(self) -> None:
        if self.app.snap.get("overrideActive"):
            self.app.send({"cmd": "cancel_override"})

    def action_switch_tab(self) -> None:
        tabs = self.query_one(TabbedContent)
        if tabs.active == "tracks-tab":
            tabs.active = "plugins-tab"
            switches = [s for s in self.query(PluginSwitch) if not s.disabled]
            if switches:
                switches[0].focus()
        else:
            tabs.active = "tracks-tab"
            self.query_one(DataTable).focus()
        self.refresh_bindings()

    def on_plugin_switch_toggle(self, message: PluginSwitch.Toggle) -> None:
        self.app.send({"cmd": "toggle_plugin", "name": message.plugin})

    # ---- rendering -------------------------------------------------------

    def refresh_header(self) -> None:
        snap = self.app.snap
        if not snap:
            return
        self.query_one("#header", Static).update(
            format_header(snap.get("episode"), snap.get("onAirSince"), datetime.now()))

    def render_snapshot(self, snap: dict) -> None:
        self.refresh_header()
        self._render_now_playing(snap)
        self._render_tracks(snap)
        self._render_plugins(snap)
        self.render_status()
        self.refresh_bindings()

    def _render_now_playing(self, snap):
        np = snap.get("nowPlaying")
        override = bool(snap.get("overrideActive"))
        self.query_one("#now-playing").set_class(override, "override")
        if np is None:
            title, length, album, source = "Nothing playing", "", "", ""
        else:
            title = f"▶ {np.get('title') or ''} — {np.get('artist') or ''}"
            length, album = np.get("length") or "", np.get("album") or ""
            source = {"swinsian": "source: Swinsian",
                      "stop": "source: stopped"}.get(np.get("source"), "")
        if override:
            source = "OVERRIDE — until Swinsian resumes"
        self.query_one("#np-title", Static).update(Text(title))
        self.query_one("#np-length", Static).update(Text(length))
        self.query_one("#np-album", Static).update(Text(album))
        self.query_one("#np-source", Static).update(Text(source))

    def _render_tracks(self, snap):
        table = self.query_one(DataTable)
        prev = self.app.prev_snap
        prev_tracks = prev.get("tracks") or []
        follow_targets = {prev.get("currentRowid")}
        if prev_tracks:
            follow_targets.add(prev_tracks[-1]["rowid"])
        cursor_rowid = None
        if table.row_count:
            cursor_rowid = int(
                table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)
        follow = not prev_tracks or cursor_rowid in follow_targets

        tracks = snap.get("tracks") or []
        current = snap.get("currentRowid")
        table.clear()
        for n, row in enumerate(tracks, 1):
            style = "dim" if row.get("ignore") else ""
            if row["rowid"] == current:
                style += " bold green"
            cells = (str(n), _clock(row.get("startTime")), row.get("length") or "",
                     row.get("title") or "", row.get("artist") or "")
            table.add_row(*(Text(c, style=style) for c in cells), key=str(row["rowid"]))
        if not tracks:
            return
        rowids = [row["rowid"] for row in tracks]
        if follow:
            target = current if current in rowids else rowids[-1]
        else:
            target = cursor_rowid if cursor_rowid in rowids else rowids[-1]
        table.move_cursor(row=rowids.index(target), scroll=follow)

    def _render_plugins(self, snap):
        plugins = snap.get("plugins") or []
        shape = [(p["name"], p["kind"], bool(p.get("locked"))) for p in plugins]
        container = self.query_one("#plugins", VerticalScroll)
        if shape != getattr(self, "_plugin_shape", None):
            self._plugin_shape = shape
            container.remove_children()
            widgets = []
            for kind, heading in (("live", "Live"), ("file", "Generated at end of show")):
                group = [p for p in plugins if p["kind"] == kind]
                if not group:
                    continue
                widgets.append(Label(heading, classes="plugin-group"))
                for p in group:
                    label = p["name"] + ("  (always on)" if p.get("locked") else "")
                    widgets.append(Horizontal(
                        PluginSwitch(value=bool(p["enabled"]), animate=False,
                                     name=p["name"], disabled=bool(p.get("locked"))),
                        Label(label, classes="plugin-name"),
                        classes="plugin-row"))
            container.mount_all(widgets)
            return
        switches = {switch.name: switch for switch in self.query(PluginSwitch)}
        for p in plugins:
            if p["name"] in switches:
                switches[p["name"]].value = bool(p["enabled"])

    def render_status(self) -> None:
        status = self.app.link_status
        error = self.app.snap.get("lastError")
        if status != CONNECTED:
            text = Text(status or "connecting…", style="bold red")
        elif error:
            text = Text(error, style="yellow")
        else:
            text = Text("connected", style="dim")
        self.query_one("#status", Static).update(text)


def _clock(start_time) -> str:
    if not start_time:
        return ""
    try:
        return datetime.fromisoformat(start_time).strftime("%H:%M:%S")
    except ValueError:
        return str(start_time)


class TrackUpdateApp(App):
    CSS_PATH = "tui.tcss"
    TITLE = "trackupdate"

    def __init__(self, link):
        super().__init__()
        self.link = link
        self.snap: dict = {}
        self.prev_snap: dict = {}
        self.rows: dict[int, dict] = {}
        self.link_status: str | None = None
        self._outbox: asyncio.Queue = asyncio.Queue()

    def get_default_screen(self) -> Screen:
        return MainScreen()

    def on_ready(self) -> None:
        # Ready, not mount: the main screen's widgets must exist first.
        self.run_worker(self._consume(), name="engine-link", exclusive=True)
        self.run_worker(self._send_loop(), name="engine-send")
        self.set_interval(1.0, self._tick)

    def _main(self) -> MainScreen:
        return self.screen_stack[0]

    def _tick(self) -> None:
        # Timer exceptions would exit the app, so none may escape.
        try:
            self._main().refresh_header()
        except Exception as e:
            self.log.error(f"header refresh failed: {e!r}")

    # ---- link ------------------------------------------------------------

    async def _consume(self) -> None:
        while True:
            try:
                async for msg in self.link:
                    self._handle(msg)
            except Exception as e:
                self.log.error(f"engine link failed: {e!r}")
                self._set_link_status(DISCONNECTED)
            await asyncio.sleep(1.0)

    def _handle(self, msg: dict) -> None:
        try:
            event = msg.get("event")
            if event == "link":
                self._set_link_status(msg.get("status"))
            elif event == "snapshot":
                self.apply_snapshot(msg)
        except Exception as e:
            self.log.error(f"could not render engine message: {e!r}")

    def _set_link_status(self, status) -> None:
        self.link_status = status
        self._main().render_status()

    def send(self, cmd: dict) -> None:
        """Queue a command for the engine; never blocks or raises."""
        self._outbox.put_nowait(cmd)

    async def _send_loop(self) -> None:
        while True:
            cmd = await self._outbox.get()
            try:
                await self.link.send(cmd)
            except Exception as e:
                self.log.error(f"send failed: {e!r}")
                self.link_status = DISCONNECTED
                self._main().render_status()

    # ---- snapshots -------------------------------------------------------

    def apply_snapshot(self, snap: dict) -> None:
        self.prev_snap, self.snap = self.snap, snap
        self.rows = {row["rowid"]: row for row in snap.get("tracks") or []}
        self.link_status = CONNECTED  # snapshots only arrive over a live link
        self._main().render_snapshot(snap)
