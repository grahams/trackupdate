"""Replay an episode's rows through the archive-capable plugins."""
from datetime import datetime

import episode_db


def generate(config, episode, plugin_classes, conn):
    """Run every archive-enabled plugin over the episode; one result per plugin.

    A failure in one plugin is recorded and does not stop the others.
    """
    rows = episode_db.list_rows(conn, episode)
    if not rows:
        return []
    first = episode_db.first_start_time(conn, episode)

    results = []
    for cls in plugin_classes:
        if not cls.enableArchive:
            continue
        name = cls.__name__
        try:
            plugin = cls(config, episode, first)
            try:
                previous = None
                for row in rows:
                    # legacy behaviour: skip a row repeating the previous track
                    key = (row["artist"], row["title"])
                    if key == previous:
                        continue
                    previous = key
                    plugin.logTrack(episode_db.row_to_track(row),
                                    datetime.fromisoformat(row["startTime"]))
            finally:
                plugin.close()
            results.append({"plugin": name, "ok": True, "error": None})
        except Exception as e:
            results.append({"plugin": name, "ok": False, "error": str(e)})
    return results
