import asyncio
import os
import tempfile
from datetime import datetime

from textual.widgets import Button, DataTable, Input, Static, Switch

import runtime
from tui import (DISCONNECTED, EndingScreen, EngineLink, MainScreen, QuitScreen,
                 TrackUpdateApp, format_header)


class FakeLink:
    """Stands in for EngineLink: yields scripted messages, records sends."""

    def __init__(self, messages=()):
        self.messages = list(messages)
        self.sent = []

    async def send(self, cmd):
        self.sent.append(cmd)

    async def __aiter__(self):
        for msg in self.messages:
            yield msg
        await asyncio.Event().wait()


def track(rowid, title, artist="Artist", album="Album", ignore=False,
          start="2026-10-21 20:00:12.000000", length="3:00"):
    return {"rowid": rowid, "uniqueId": f"u{rowid}", "title": title,
            "artist": artist, "album": album, "length": length,
            "startTime": start, "ignore": ignore, "artworkUrl": None}


def snapshot(**over):
    snap = {
        "event": "snapshot", "episode": "412", "phase": "live",
        "onAirSince": "2026-10-21 20:00:12.000000",
        "nowPlaying": {"title": "Pale Blue Eyes", "artist": "The Velvet Underground",
                       "album": "The Velvet Underground", "length": "3:41",
                       "source": "swinsian"},
        "overrideActive": False,
        "currentRowid": 3,
        "tracks": [
            track(1, "Show Intro", ignore=True),
            track(2, "Teh Killing Moon", "Echo & the Bunnymen", "Ocean Rain",
                  start="2026-10-21 20:03:10.000000"),
            track(3, "Pale Blue Eyes", "The Velvet Underground",
                  "The Velvet Underground", start="2026-10-21 20:08:51.000000"),
        ],
        "plugins": [
            {"name": "SqliteTarget", "kind": "live", "enabled": True, "locked": True},
            {"name": "AudioHijackTarget", "kind": "live", "enabled": True, "locked": False},
            {"name": "CueFileTarget", "kind": "file", "enabled": False, "locked": False},
        ],
        "lastError": None, "results": [],
    }
    snap.update(over)
    return snap


def run(coro):
    asyncio.run(coro)


async def wait_until(pilot, cond, tries=50):
    for _ in range(tries):
        if cond():
            return
        await pilot.pause(0.01)
    assert cond()


def test_format_header():
    now = datetime(2026, 10, 21, 21, 12, 56)
    assert (format_header("412", "2026-10-21 20:00:12.000000", now)
            == "trackupdate · Episode 412 · on air 01:12:44")
    assert format_header("412", None, now) == "trackupdate · Episode 412 · not on air yet"


def test_tracks_table_renders_snapshot():
    async def body():
        app = TrackUpdateApp(FakeLink([snapshot()]))
        async with app.run_test(size=(110, 30)) as pilot:
            table = app.query_one(DataTable)
            await wait_until(pilot, lambda: table.row_count == 3)
            ignored = table.get_row("1")
            assert all("dim" in str(cell.style) for cell in ignored)
            normal = table.get_row("2")
            assert not any("dim" in str(cell.style) for cell in normal)
            assert str(normal[3]) == "Teh Killing Moon"
            # the current row is highlighted and the cursor follows it
            assert any("bold" in str(cell.style) for cell in table.get_row("3"))
            assert table.cursor_row == 2
    run(body())


def test_cursor_stays_put_unless_on_last_row():
    async def body():
        app = TrackUpdateApp(FakeLink())
        async with app.run_test(size=(110, 30)) as pilot:
            table = app.query_one(DataTable)
            app.apply_snapshot(snapshot())
            await pilot.pause()
            assert table.cursor_row == 2
            new = snapshot()
            new["tracks"] = new["tracks"] + [track(4, "Next", start="2026-10-21 20:12:11.000000")]
            new["currentRowid"] = 4
            app.apply_snapshot(new)
            await pilot.pause()
            assert table.cursor_row == 3  # followed
            table.move_cursor(row=1)
            newer = dict(new, tracks=new["tracks"] + [track(5, "After")], currentRowid=5)
            app.apply_snapshot(newer)
            await pilot.pause()
            assert table.cursor_row == 1  # user scrolled up: stays on row 2
    run(body())


def test_edit_sends_edit_row():
    async def body():
        link = FakeLink([snapshot()])
        app = TrackUpdateApp(link)
        async with app.run_test(size=(110, 30)) as pilot:
            table = app.query_one(DataTable)
            await wait_until(pilot, lambda: table.row_count == 3)
            table.focus()
            table.move_cursor(row=1)
            await pilot.press("e")
            await pilot.pause()
            title = app.screen.query_one("#title", Input)
            assert title.value == "Teh Killing Moon"
            assert app.screen.query_one("#artist", Input).value == "Echo & the Bunnymen"
            title.value = "The Killing Moon"
            title.focus()
            await pilot.press("enter")
            await wait_until(pilot, lambda: link.sent)
            assert link.sent == [{"cmd": "edit_row", "rowid": 2,
                                      "title": "The Killing Moon",
                                      "artist": "Echo & the Bunnymen",
                                      "album": "Ocean Rain"}]
    run(body())


def test_toggle_ignore_sends_selected_rowid():
    async def body():
        link = FakeLink([snapshot()])
        app = TrackUpdateApp(link)
        async with app.run_test(size=(110, 30)) as pilot:
            table = app.query_one(DataTable)
            await wait_until(pilot, lambda: table.row_count == 3)
            table.move_cursor(row=0)
            await pilot.press("i")
            await wait_until(pilot, lambda: link.sent)
            assert link.sent == [{"cmd": "toggle_ignore", "rowid": 1}]
    run(body())


def test_override_modal_sends_set_override():
    async def body():
        link = FakeLink([snapshot()])
        app = TrackUpdateApp(link)
        async with app.run_test(size=(110, 30)) as pilot:
            await wait_until(pilot, lambda: app.query_one(DataTable).row_count == 3)
            await pilot.press("o")
            await pilot.pause()
            for key, value in [("title", "Vinyl Side A"), ("artist", "Somebody"),
                               ("album", "LP"), ("length", "20:00")]:
                app.screen.query_one(f"#{key}", Input).value = value
            app.screen.query_one("#title", Input).focus()
            await pilot.press("enter")
            await wait_until(pilot, lambda: link.sent)
            assert link.sent == [{"cmd": "set_override", "title": "Vinyl Side A",
                                  "artist": "Somebody", "album": "LP",
                                  "length": "20:00"}]
    run(body())


def test_override_card_turns_orange():
    async def body():
        app = TrackUpdateApp(FakeLink())
        async with app.run_test(size=(110, 30)) as pilot:
            app.apply_snapshot(snapshot(
                overrideActive=True,
                nowPlaying={"title": "Vinyl", "artist": "Somebody", "album": "LP",
                            "length": "20:00", "source": "override"}))
            await pilot.pause()
            card = app.query_one("#now-playing")
            assert card.has_class("override")
            assert "OVERRIDE — until Swinsian resumes" in str(
                app.query_one("#np-source", Static).render())
            app.apply_snapshot(snapshot())
            await pilot.pause()
            assert not card.has_class("override")
    run(body())


def test_cancel_key_only_when_override_active():
    async def body():
        link = FakeLink()
        app = TrackUpdateApp(link)
        async with app.run_test(size=(110, 30)) as pilot:
            app.apply_snapshot(snapshot())
            await pilot.pause()
            await pilot.press("x")
            await pilot.pause()
            assert link.sent == []
            app.apply_snapshot(snapshot(overrideActive=True))
            await pilot.pause()
            await pilot.press("x")
            await wait_until(pilot, lambda: link.sent)
            assert link.sent == [{"cmd": "cancel_override"}]
    run(body())


def test_sqlite_switch_disabled():
    async def body():
        app = TrackUpdateApp(FakeLink([snapshot()]))
        async with app.run_test(size=(110, 30)) as pilot:
            await wait_until(pilot, lambda: len(app.query(Switch)) == 3)
            switches = {s.name: s for s in app.query(Switch)}
            assert switches["SqliteTarget"].disabled
            assert not switches["AudioHijackTarget"].disabled
            assert switches["AudioHijackTarget"].value is True
            assert switches["CueFileTarget"].value is False
    run(body())


def test_space_on_switch_sends_toggle_plugin_without_local_change():
    async def body():
        link = FakeLink([snapshot()])
        app = TrackUpdateApp(link)
        async with app.run_test(size=(110, 30)) as pilot:
            await wait_until(pilot, lambda: len(app.query(Switch)) == 3)
            await pilot.press("tab")  # to the Plugins tab
            await pilot.pause()
            switch = next(s for s in app.query(Switch) if s.name == "CueFileTarget")
            switch.focus()
            await pilot.press("space")
            await wait_until(pilot, lambda: link.sent)
            assert link.sent == [{"cmd": "toggle_plugin", "name": "CueFileTarget"}]
            assert switch.value is False  # display follows the next snapshot
            snap = snapshot()
            snap["plugins"][2]["enabled"] = True
            app.apply_snapshot(snap)
            await pilot.pause()
            assert switch.value is True
            await pilot.press("i")  # row keys do nothing on the Plugins tab
            await pilot.pause()
            assert link.sent == [{"cmd": "toggle_plugin", "name": "CueFileTarget"}]
    run(body())


def test_status_line_shows_link_status_and_last_error():
    async def body():
        app = TrackUpdateApp(FakeLink([
            {"event": "link", "status": "disconnected — retrying"}]))
        async with app.run_test(size=(110, 30)) as pilot:
            status = app.query_one("#status", Static)
            await wait_until(pilot, lambda: "retrying" in str(status.render()))
            app.apply_snapshot(snapshot(lastError="Swinsian poll failed (see engine.log)"))
            await pilot.pause()
            assert "Swinsian poll failed" in str(status.render())
    run(body())


def test_engine_link_sends_hello_and_yields_messages():
    async def body():
        d = tempfile.mkdtemp()
        path = os.path.join(d, "e.sock")
        received = []

        async def handle(reader, writer):
            received.append(runtime.decode(await reader.readline()))
            writer.write(runtime.encode(snapshot()))
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_unix_server(handle, path=path)
        link = EngineLink(path, retry_delay=0.01)
        it = link.__aiter__()
        assert await it.__anext__() == {"event": "link", "status": "connected"}
        assert (await it.__anext__())["event"] == "snapshot"
        assert received == [{"cmd": "hello"}]
        # the server closed the connection: the link reports it and retries
        assert await it.__anext__() == {"event": "link", "status": DISCONNECTED}
        assert await it.__anext__() == {"event": "link", "status": "connected"}
        await it.aclose()
        server.close()
        await server.wait_closed()
    run(body())


def test_engine_link_reports_retrying_when_no_engine():
    async def body():
        path = os.path.join(tempfile.mkdtemp(), "missing.sock")
        it = EngineLink(path, retry_delay=0.01).__aiter__()
        assert await it.__anext__() == {"event": "link", "status": DISCONNECTED}
        assert await it.__anext__() == {"event": "link", "status": DISCONNECTED}
        await it.aclose()
    run(body())


def test_format_header_survives_bad_on_air_since():
    now = datetime(2026, 10, 21, 21, 0, 0)
    assert format_header("412", "garbage", now) == "trackupdate · Episode 412"
    assert format_header("412", 5, now) == "trackupdate · Episode 412"


def test_bad_on_air_since_does_not_kill_the_app():
    async def body():
        app = TrackUpdateApp(FakeLink())
        async with app.run_test(size=(110, 30)) as pilot:
            header = app.query_one("#header", Static)
            for bad in ("garbage", 5):
                app.apply_snapshot(snapshot(onAirSince=bad))
                app._tick()
                await pilot.pause(1.2)  # let the real 1 s timer fire too
                assert app.is_running
                assert "Episode 412" in str(header.render())
    run(body())


# ---- quitting, ending the show, resilience ---------------------------------

def test_ctrl_c_opens_quit_screen_focused_on_cancel():
    async def body():
        app = TrackUpdateApp(FakeLink([snapshot()]))
        async with app.run_test(size=(110, 30)) as pilot:
            await wait_until(pilot, lambda: app.query_one(DataTable).row_count == 3)
            await pilot.press("ctrl+c")
            await pilot.pause()
            assert isinstance(app.screen, QuitScreen)
            labels = [str(b.label) for b in app.screen.query(Button)]
            assert labels == ["End show", "Close window", "Cancel"]
            assert app.focused.id == "cancel"
            await pilot.press("ctrl+c")  # already open: no second prompt
            await pilot.pause()
            assert len(app.screen_stack) == 2
    run(body())


def test_q_and_ctrl_q_open_quit_screen():
    async def body():
        app = TrackUpdateApp(FakeLink([snapshot()]))
        async with app.run_test(size=(110, 30)) as pilot:
            await wait_until(pilot, lambda: app.query_one(DataTable).row_count == 3)
            for key in ("q", "ctrl+q"):
                await pilot.press(key)
                await pilot.pause()
                assert isinstance(app.screen, QuitScreen)
                await pilot.press("escape")
                await pilot.pause()
                assert isinstance(app.screen, MainScreen)
            assert app.is_running
    run(body())


def test_q_types_into_track_form_but_ctrl_c_still_prompts():
    async def body():
        app = TrackUpdateApp(FakeLink([snapshot()]))
        async with app.run_test(size=(110, 30)) as pilot:
            await wait_until(pilot, lambda: app.query_one(DataTable).row_count == 3)
            await pilot.press("o")
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            assert app.screen.query_one("#title", Input).value == "q"
            await pilot.press("ctrl+c")
            await pilot.pause()
            assert isinstance(app.screen, QuitScreen)
    run(body())


def test_enter_on_quit_screen_cancels():
    async def body():
        link = FakeLink([snapshot()])
        app = TrackUpdateApp(link)
        async with app.run_test(size=(110, 30)) as pilot:
            await wait_until(pilot, lambda: app.query_one(DataTable).row_count == 3)
            await pilot.press("ctrl+c")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause(0.05)
            assert isinstance(app.screen, MainScreen)
            assert app.is_running
            assert link.sent == []
    run(body())


def test_end_show_sends_and_shows_results():
    async def body():
        link = FakeLink([snapshot()])
        app = TrackUpdateApp(link)
        async with app.run_test(size=(110, 30)) as pilot:
            await wait_until(pilot, lambda: app.query_one(DataTable).row_count == 3)
            await pilot.press("ctrl+c")
            await pilot.pause()
            await pilot.click("#end")
            await wait_until(pilot, lambda: link.sent)
            assert link.sent == [{"cmd": "end_show"}]
            assert isinstance(app.screen, EndingScreen)
            message = app.screen.query_one("#ending-message", Static)
            assert "generating files" in str(message.render())
            app.apply_snapshot(snapshot(phase="ending"))
            await pilot.pause()
            await pilot.press("x")  # keys do nothing until the results arrive
            await pilot.pause()
            assert app.is_running
            app.apply_snapshot(snapshot(phase="ended", results=[
                {"plugin": "CueFileTarget", "ok": True, "error": None},
                {"plugin": "HugoBlogTarget", "ok": False, "error": "disk full"}]))
            await pilot.pause()
            app._handle({"event": "link", "status": DISCONNECTED})  # engine exits
            await pilot.pause()
            text = str(app.screen.query_one("#ending-message", Static).render())
            assert "✓ CueFileTarget" in text
            assert "✗ HugoBlogTarget — disk full" in text
            assert "press any key to exit" in text
            assert "retrying" not in text
            await pilot.press("x")
            await pilot.pause()
            assert not app.is_running
    run(body())


def test_engine_closing_before_results_says_so():
    async def body():
        link = FakeLink([snapshot()])
        app = TrackUpdateApp(link)
        async with app.run_test(size=(110, 30)) as pilot:
            await wait_until(pilot, lambda: app.query_one(DataTable).row_count == 3)
            await pilot.press("ctrl+c")
            await pilot.pause()
            await pilot.click("#end")
            await wait_until(pilot, lambda: link.sent)
            app.apply_snapshot(snapshot(phase="ending"))
            app._handle({"event": "link", "status": DISCONNECTED})
            await pilot.pause()
            text = str(app.screen.query_one("#ending-message", Static).render())
            assert "Engine closed before reporting results" in text
            assert "engine.log" in text
            await pilot.press("space")
            await pilot.pause()
            assert not app.is_running
    run(body())


def test_ended_snapshot_on_fresh_connect_shows_results():
    async def body():
        app = TrackUpdateApp(FakeLink([snapshot(phase="ended", results=[
            {"plugin": "CueFileTarget", "ok": True, "error": None}])]))
        async with app.run_test(size=(110, 30)) as pilot:
            await wait_until(pilot, lambda: isinstance(app.screen, EndingScreen)
                             and app.screen.query("#ending-message"))
            text = str(app.screen.query_one("#ending-message", Static).render())
            assert "✓ CueFileTarget" in text
    run(body())


def test_close_window_sends_nothing():
    async def body():
        link = FakeLink([snapshot()])
        app = TrackUpdateApp(link)
        async with app.run_test(size=(110, 30)) as pilot:
            await wait_until(pilot, lambda: app.query_one(DataTable).row_count == 3)
            await pilot.press("ctrl+c")
            await pilot.pause()
            await pilot.click("#close")
            await pilot.pause(0.05)
            assert not app.is_running
            assert link.sent == []
    run(body())


class FlakyLink(FakeLink):
    """Refuses the first connection, then behaves like FakeLink."""

    def __init__(self, messages=()):
        super().__init__(messages)
        self.connects = 0

    async def connect(self):
        self.connects += 1
        if self.connects == 1:
            raise ConnectionRefusedError("no engine yet")

    async def __aiter__(self):
        await self.connect()
        async for msg in super().__aiter__():
            yield msg


def test_link_drop_shows_retrying_without_crash():
    async def body():
        link = FlakyLink([snapshot()])
        app = TrackUpdateApp(link)
        async with app.run_test(size=(110, 30)) as pilot:
            status = app.query_one("#status", Static)
            await wait_until(pilot, lambda: "retrying" in str(status.render()))
            assert app.is_running
            await wait_until(pilot, lambda: app.query_one(DataTable).row_count == 3,
                             tries=200)
            assert link.connects == 2
            assert "connected" == str(status.render())
    run(body())
