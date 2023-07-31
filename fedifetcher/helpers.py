"""Helper functions for fedifetcher."""
import logging
import sys
import time
from datetime import UTC, datetime

import colorlog
import requests
from dateutil import parser

from .argparser import arguments


def setup_logging() -> None:
    """Set logging."""
    logger = logging.getLogger()
    stdout = colorlog.StreamHandler(stream=sys.stdout)
    fmt = colorlog.ColoredFormatter(
    "%(white)s%(asctime)s%(reset)s | %(log_color)s%(levelname)s%(reset)s | \
%(threadName)s:%(name)s | %(blue)s%(filename)s:%(lineno)s%(reset)s | %(funcName)s >>> \
%(log_color)s%(message)s%(reset)s")
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
    TEAPOT = 418
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
        h["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 +https://github.com/Teqed Meowstodon/1.0.0"  # noqa: E501

    if timeout == 0:
        timeout = arguments.http_timeout

    try:
        response = requests.get(url, headers=h, timeout=timeout)
    except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout):
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
