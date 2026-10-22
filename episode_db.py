"""Rowid-addressed helpers for one episode's rows in the trackupdate table.

Rows are identified by SQLite rowid (not uniqueId) because the same track can
appear twice in one episode. Every write commits immediately.
"""
from datetime import datetime

from Track import Track

_COLUMNS = 'rowid, uniqueId, title, artist, album, length, startTime, "ignore", artworkUrl'
_KEYS = ("rowid", "uniqueId", "title", "artist", "album", "length",
         "startTime", "ignore", "artworkUrl")


def _to_dict(values):
    row = dict(zip(_KEYS, values))
    row["ignore"] = bool(row["ignore"])
    return row


def list_rows(conn, episode):
    cur = conn.execute(
        f'SELECT {_COLUMNS} FROM trackupdate WHERE episodeNumber = ? '
        'ORDER BY startTime, rowid', (episode,))
    return [_to_dict(r) for r in cur.fetchall()]


def last_row(conn, episode):
    row = conn.execute(
        f'SELECT {_COLUMNS} FROM trackupdate WHERE episodeNumber = ? '
        'ORDER BY startTime DESC, rowid DESC LIMIT 1', (episode,)).fetchone()
    return _to_dict(row) if row else None


def first_start_time(conn, episode):
    row = conn.execute(
        'SELECT MIN(startTime) FROM trackupdate WHERE episodeNumber = ?',
        (episode,)).fetchone()
    return datetime.fromisoformat(row[0]) if row and row[0] else None


def update_text(conn, rowid, title, artist, album):
    conn.execute(
        'UPDATE trackupdate SET title = ?, artist = ?, album = ? WHERE rowid = ?',
        (title, artist, album, rowid))
    conn.commit()


def set_ignore(conn, rowid, ignore):
    conn.execute('UPDATE trackupdate SET "ignore" = ? WHERE rowid = ?',
                 (1 if ignore else 0, rowid))
    conn.commit()


def row_to_track(row):
    return Track(
        title=row["title"], artist=row["artist"], album=row["album"],
        length=row["length"], artworkURL=row["artworkUrl"],
        uniqueId=row["uniqueId"], ignore=bool(row["ignore"]))
