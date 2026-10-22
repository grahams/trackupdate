import sqlite3
from datetime import datetime

import pytest

import episode_db
from db_schema import ensure_schema
from Track import Track


def _insert(conn, episode, uid, title, start, ignore=0, artwork="art"):
    conn.execute(
        'INSERT INTO trackupdate (episodeNumber, uniqueId, title, artist, album, '
        'length, startTime, "ignore", artworkUrl) VALUES (?,?,?,?,?,?,?,?,?)',
        (episode, uid, title, "artist", "album", "180", start, ignore, artwork),
    )
    conn.commit()


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ensure_schema(c)
    _insert(c, 412, "u2", "second", "2026-10-21 20:05:00.000000")
    _insert(c, 412, "u1", "first", "2026-10-21 20:00:12.000000")
    _insert(c, 413, "u9", "other", "2026-10-22 20:00:00.000000")
    yield c
    c.close()


def test_list_rows_orders_by_start_and_filters_episode(conn):
    rows = episode_db.list_rows(conn, 412)
    assert [r["title"] for r in rows] == ["first", "second"]
    assert set(rows[0]) == {"rowid", "uniqueId", "title", "artist", "album",
                            "length", "startTime", "ignore", "artworkUrl"}
    assert rows[0]["ignore"] is False


def test_last_row_none_for_empty_episode(conn):
    assert episode_db.last_row(conn, 999) is None
    assert episode_db.last_row(conn, 412)["title"] == "second"


def test_first_start_time_parses_space_form(conn):
    assert episode_db.first_start_time(conn, 412) == datetime(2026, 10, 21, 20, 0, 12)
    assert episode_db.first_start_time(conn, 999) is None


def test_update_text_changes_only_that_row(conn):
    _insert(conn, 414, "dup", "a", "2026-10-23 20:00:00.000000")
    _insert(conn, 414, "dup", "b", "2026-10-23 20:01:00.000000")
    first, second = episode_db.list_rows(conn, 414)
    episode_db.update_text(conn, first["rowid"], "T", "A", "L")
    first, second = episode_db.list_rows(conn, 414)
    assert (first["title"], first["artist"], first["album"]) == ("T", "A", "L")
    assert (second["title"], second["artist"], second["album"]) == ("b", "artist", "album")


def test_set_ignore_roundtrip(conn):
    rowid = episode_db.list_rows(conn, 412)[0]["rowid"]
    episode_db.set_ignore(conn, rowid, True)
    assert episode_db.list_rows(conn, 412)[0]["ignore"] is True
    episode_db.set_ignore(conn, rowid, False)
    assert episode_db.list_rows(conn, 412)[0]["ignore"] is False


def test_row_to_track(conn):
    _insert(conn, 415, "u", "t", "2026-10-24 20:00:00.000000", ignore=1)
    row = episode_db.last_row(conn, 415)
    assert episode_db.row_to_track(row) == Track(
        title="t", artist="artist", album="album", length="180",
        artworkURL="art", uniqueId="u", ignore=True)
