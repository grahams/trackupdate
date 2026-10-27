"""Track source helpers: Swinsian polling and iTunes artwork lookup."""

import json
import logging
import os
import re
import subprocess
from urllib.parse import quote

import requests
import urllib3.util.connection

GRABBER_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "util", "swinsian-track-grabber"
)


def set_ipv6(enabled: bool) -> None:
    """Let requests use IPv6, or restrict it to IPv4 addresses.

    requests tries a host's addresses one at a time, so a broken IPv6 route
    stalls every lookup until each IPv6 address times out.
    """
    urllib3.util.connection.HAS_IPV6 = enabled


def poll_swinsian(grabber=GRABBER_PATH, run=subprocess.check_output):
    """Return the parsed grabber JSON ({} when idle), or None on failure."""
    try:
        out = run([grabber], text=True, timeout=10)
        return json.loads(out)
    except subprocess.TimeoutExpired:
        logging.warning("Swinsian grabber timed out")
    except subprocess.CalledProcessError as e:
        logging.warning(f"Swinsian grabber failed: {e}")
    except json.JSONDecodeError as e:
        logging.warning(f"Swinsian grabber returned invalid JSON: {e}")
    return None


def search_artwork(title, artist):
    url500 = None

    try:
        searchTerm = quote(f"{artist} {title}")
        searchUrl = f'https://itunes.apple.com/search?term={searchTerm}&entity=song&limit=1'
        trackSearch = requests.get(searchUrl, timeout=5).json()

        if trackSearch['resultCount'] > 0:
            url100 = trackSearch["results"][0]["artworkUrl100"]
            url500 = re.sub(r'100x100', '500x500', url100)
    except requests.exceptions.RequestException as e:
        logging.warning(f"Cover image search failed: {e}")
    except json.JSONDecodeError as e:
        logging.warning(f"Cover image JSON decode failed: {e}")

    return url500
