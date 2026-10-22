import configparser
import os
import sqlite3
from datetime import datetime

import pytest

import archive
import db_schema
import plugin_loader

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "plugins")


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    db_schema.ensure_schema(c)
    rows = [(7, "a", "One", "A", "Al", "1", "2026-01-01 10:00:00.000000", 0, "u1"),
            (7, "b", "Two", "B", "Al", "2", "2026-01-01 10:05:00.000000", 0, "u2"),
            (8, "c", "Other", "C", "Al", "3", "2026-01-02 10:00:00.000000", 0, "u3")]
    c.executemany("INSERT INTO trackupdate VALUES (?,?,?,?,?,?,?,?,?)", rows)
    c.commit()
    return c


@pytest.fixture
def classes():
    config = configparser.ConfigParser()
    for name in ("LiveFake", "FileFake", "BrokenFake"):
        config.add_section(name)
        config.set(name, "enabled", "True")
    plugin_classes = plugin_loader.discover(config, FIXTURES)
    import FileFake
    FileFake.calls.clear()
    yield config, plugin_classes
    FileFake.calls.clear()


def test_generate_feeds_rows_in_order(conn, classes):
    import FileFake
    config, plugin_classes = classes
    archive.generate(config, 7, [c for c in plugin_classes if c.__name__ == "FileFake"], conn)
    assert FileFake.calls == [
        ("init", 7, datetime(2026, 1, 1, 10, 0, 0)),
        ("track", "One", datetime(2026, 1, 1, 10, 0, 0)),
        ("track", "Two", datetime(2026, 1, 1, 10, 5, 0)),
        ("close",),
    ]


def test_generate_isolates_failures(conn, classes):
    import FileFake
    config, plugin_classes = classes
    results = archive.generate(config, 7, plugin_classes, conn)
    assert [(r["plugin"], r["ok"]) for r in results] == [
        ("BrokenFake", False), ("FileFake", True)]
    assert results[0]["error"] == "boom"
    assert results[1]["error"] is None
    assert [c[1] for c in FileFake.calls if c[0] == "track"] == ["One", "Two"]
    assert FileFake.calls[-1] == ("close",)


def test_generate_skips_live_plugins(conn, classes):
    config, plugin_classes = classes
    results = archive.generate(config, 7, plugin_classes, conn)
    assert "LiveFake" not in [r["plugin"] for r in results]


def test_generate_empty_episode(conn, classes):
    config, plugin_classes = classes
    assert archive.generate(config, 99, plugin_classes, conn) == []
