"""Single source of truth for the trackupdate sqlite schema.

Imported by SqliteTarget (live writer), web_editor (UI),
util/m3u_import (playlist importer), and util/timeshift (scratch tool).
"""

CREATE_TRACKUPDATE_TABLE = '''
    CREATE TABLE IF NOT EXISTS trackupdate (
        episodeNumber integer NOT NULL,
        uniqueId char(128),
        title char(128),
        artist char(128),
        album char(128),
        length char(128),
        startTime timestamp(128),
        "ignore" integer(128) NOT NULL DEFAULT(0),
        artworkUrl text(128)
    );
'''


def ensure_schema(conn):
    """Create the trackupdate table on `conn` if it does not exist."""
    conn.execute(CREATE_TRACKUPDATE_TABLE)
    conn.commit()
