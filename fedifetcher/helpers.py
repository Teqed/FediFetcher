"""Helper functions for fedifetcher."""
import json
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import colorlog
import requests
from dateutil import parser

from fedifetcher.ordered_set import OrderedSet

from .argparser import arguments


def setup_logging() -> None:
    """Set logging."""
    logger = logging.getLogger()
    stdout = colorlog.StreamHandler(stream=sys.stdout)
    fmt = colorlog.ColoredFormatter(
    "%(white)s%(asctime)s%(reset)s | %(log_color)s%(levelname)s%(reset)s | \
%(blue)s%(filename)s:%(lineno)s%(reset)s >>> %(log_color)s%(message)s%(reset)s")
    stdout.setFormatter(fmt)
    logger.addHandler(stdout)
    logger.setLevel(arguments.log_level)

class Response:
    """HTTP response codes."""

    OK = 200
    CREATED = 201
    ACCEPTED = 202
    FOUND = 302
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    TOO_MANY_REQUESTS = 429
    INTERNAL_SERVER_ERROR = 500

def get(
        url : str,
        headers : dict | None = None,
        timeout : int = 0,
        max_tries : int = 2,
        ) -> requests.Response:
    """Get a URL.

    A simple wrapper to make a get request while providing our user agent, \
        and respecting rate limits.
    """
    logging.warning(f"Getting {url}")
    if headers is None:
        headers = {}
    h = headers.copy()
    if "User-Agent" not in h:
        h["User-Agent"] = "FediFetcher (https://go.thms.uk/mgr)"

    if timeout == 0:
        timeout = arguments.http_timeout

    try:
        response = requests.get(url, headers=h, timeout=timeout)
    except requests.exceptions.ReadTimeout:
        if max_tries > 0:
            logging.warning(f"Timeout requesting {url} Retrying...")
            return get(url, headers, timeout, max_tries - 1)
        raise
    else:
        if response.status_code == Response.TOO_MANY_REQUESTS and max_tries > 0:
            reset = parser.parse(response.headers["x-ratelimit-reset"])
            now = datetime.now(datetime.now(UTC).astimezone().tzinfo)
            wait = (reset - now).total_seconds() + 1
            logging.warning(
f"Rate Limit hit requesting {url} \
Waiting {wait} sec to retry at {response.headers['x-ratelimit-reset']}")
            time.sleep(wait)
            return get(url, headers, timeout, max_tries - 1)
        return response

def write_seen_files(  # noqa: PLR0913
        SEEN_URLS_FILE : Path,  # noqa: N803
        REPLIED_TOOT_SERVER_IDS_FILE : Path,  # noqa: N803
        KNOWN_FOLLOWINGS_FILE : Path,  # noqa: N803
        RECENTLY_CHECKED_USERS_FILE : Path,  # noqa: N803
        seen_urls : OrderedSet | None,
        replied_toot_server_ids : dict[str, str | None] | None,
        known_followings : OrderedSet | None,
        recently_checked_users : OrderedSet | None,
        ) -> None:
    """Write the seen files to disk."""
    if known_followings is not None:
        with Path(KNOWN_FOLLOWINGS_FILE).open("w", encoding="utf-8") as file:
            file.write("\n".join(list(known_followings)[-10000:]))
    if seen_urls is not None:
        with Path(SEEN_URLS_FILE).open("w", encoding="utf-8") as file:
            file.write("\n".join(list(seen_urls)[-10000:]))
    if replied_toot_server_ids is not None:
        with Path(REPLIED_TOOT_SERVER_IDS_FILE).open("w", encoding="utf-8") as file:
            json.dump(dict(list(replied_toot_server_ids.items())[-10000:]), file)
    if recently_checked_users is not None:
        with Path(RECENTLY_CHECKED_USERS_FILE).open("w", encoding="utf-8") as file:
            recently_checked_users.to_json(file.name)
