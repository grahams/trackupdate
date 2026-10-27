import configparser
import os

import plugin_loader

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "plugins")


def _config(**enabled):
    config = configparser.ConfigParser()
    for name, value in enabled.items():
        config.add_section(name)
        config.set(name, "enabled", value)
    return config


def test_discover_skips_disabled_and_sorts_by_priority():
    config = _config(LiveFake="True", FileFake="True", BrokenFake="False")
    names = [c.__name__ for c in plugin_loader.discover(config, FIXTURES)]
    assert names == ["LiveFake", "FileFake"]


def test_discover_ignores_unconfigured_plugins():
    assert plugin_loader.discover(configparser.ConfigParser(), FIXTURES) == []


def test_is_live():
    config = _config(LiveFake="True", FileFake="True")
    live, file_ = plugin_loader.discover(config, FIXTURES)
    assert plugin_loader.is_live(live)
    assert not plugin_loader.is_live(file_)


def test_discover_enables_anything_but_false():
    config = _config(LiveFake="true", FileFake="yes", BrokenFake="False")
    names = [c.__name__ for c in plugin_loader.discover(config, FIXTURES)]
    assert names == ["LiveFake", "FileFake"]


def test_sqlite_target_dispatched_first_among_live_plugins():
    real = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")
    names = [os.path.splitext(f)[0] for f in os.listdir(real) if f.endswith(".py")]
    classes = plugin_loader.discover(_config(**dict.fromkeys(names, "True")), real)
    live = [c.__name__ for c in classes if plugin_loader.is_live(c)]
    assert "AudioHijackTarget" in live
    assert live[0] == "SqliteTarget"
