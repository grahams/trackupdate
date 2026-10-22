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
