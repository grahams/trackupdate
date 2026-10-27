#!/usr/bin/env python3
"""Stand-in for util/swinsian-track-grabber: prints $FAKE_GRABBER_FILE (or {})."""
import os
import sys

path = os.environ.get("FAKE_GRABBER_FILE")
text = "{}"
if path:
    try:
        with open(path) as f:
            text = f.read() or "{}"
    except OSError:
        pass
sys.stdout.write(text)
