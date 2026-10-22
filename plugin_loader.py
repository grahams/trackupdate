"""Plugin discovery shared by the daemon, archive mode and the engine."""
import configparser
import glob
import os
import sys


def discover(config, plugin_dir, pattern="*.py"):
    """Return enabled plugin classes sorted by priority, highest first.

    The filename stem, class name and config section name must be identical.
    """
    plugin_dir = os.path.abspath(plugin_dir)
    if plugin_dir not in sys.path:
        sys.path.append(plugin_dir)

    classes = []
    for path in sorted(glob.glob(os.path.join(plugin_dir, pattern))):
        class_name = os.path.splitext(os.path.basename(path))[0]
        try:
            enabled = config.get(class_name, 'enabled')
        except (configparser.NoSectionError, configparser.NoOptionError):
            enabled = 'False'
        if enabled != 'True':
            continue
        mod = __import__(class_name, globals(), locals(), [''])
        classes.append(getattr(mod, class_name))

    classes.sort(key=lambda cls: cls.priority, reverse=True)
    return classes


def is_live(cls):
    return not cls.enableArchive
