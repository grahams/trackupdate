"""m3u import marks bumper tracks (album == ignoreAlbum) as ignored."""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "util"))
import m3u_import  # noqa: E402


@pytest.fixture
def show(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    db = tmp_path / "show.sqlite"
    for name in ("bumper.mp3", "song.mp3"):
        (tmp_path / name).write_bytes(b"")
    m3u = tmp_path / "show.m3u"
    m3u.write_text("#EXTM3U\n#EXTINF:30,Station - Bumper\nbumper.mp3\n"
                   "#EXTINF:180,Band - Song\nsong.mp3\n")
    albums = {"bumper.mp3": "Station IDs", "song.mp3": "Record"}
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(m3u_import, "get_audio_duration_ffprobe", lambda path: None)
    monkeypatch.setattr(m3u_import, "extract_audio_metadata",
                        lambda path, base: {"album": albums[os.path.basename(path)]})

    def run(ignore_album_line):
        (home / ".trackupdaterc").write_text(
            f"[trackupdate]\n{ignore_album_line}\n\n"
            f"[SqliteTarget]\ndbPath: {db}\n")
        monkeypatch.setattr(sys, "argv", [
            "m3u_import.py", "-e", "77", "-d", "2026-10-21 20:00:00", "-f", str(m3u)])
        m3u_import.main()
        conn = sqlite3.connect(db)
        try:
            return conn.execute('SELECT album, "ignore" FROM trackupdate '
                                "ORDER BY rowid").fetchall()
        finally:
            conn.close()
    return run


def test_ignore_album_tracks_stored_ignored(show):
    assert show("ignoreAlbum: Station IDs") == [("Station IDs", 1), ("Record", 0)]


def test_no_ignore_album_never_ignores(show):
    assert show("") == [("Station IDs", 0), ("Record", 0)]


def test_web_editor_m3u_import_marks_ignore_album(tmp_path, monkeypatch):
    import io
    web_editor = pytest.importorskip("web_editor")
    home = tmp_path / "home"
    home.mkdir()
    db = tmp_path / "show.sqlite"
    (home / ".trackupdaterc").write_text(
        f"[trackupdate]\nignoreAlbum: Station IDs\n\n[SqliteTarget]\ndbPath: {db}\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(web_editor, "get_audio_duration_ffprobe", lambda path: None)
    albums = iter(["Station IDs", "Record"])
    monkeypatch.setattr(web_editor, "extract_audio_metadata",
                        lambda path, base: {"album": next(albums)})
    m3u = b"#EXTM3U\n#EXTINF:30,Station - Bumper\nb.mp3\n#EXTINF:180,Band - Song\ns.mp3\n"
    resp = web_editor.app.test_client().post("/api/import/m3u", data={
        "file": (io.BytesIO(m3u), "show.m3u"), "episodeNumber": "77",
        "startDatetime": "2026-10-21 20:00:00"})
    assert resp.status_code == 200, resp.get_json()
    conn = sqlite3.connect(db)
    try:
        assert conn.execute('SELECT album, "ignore" FROM trackupdate '
                            "ORDER BY rowid").fetchall() == [
            ("Station IDs", 1), ("Record", 0)]
    finally:
        conn.close()
