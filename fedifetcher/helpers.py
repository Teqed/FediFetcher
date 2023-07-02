"""Helper functions for fedifetcher."""
import logging
import sys
import time
from datetime import UTC, datetime

import colorlog
import requests
from argparser import arguments
from dateutil import parser

logger = logging.getLogger()
stdout = colorlog.StreamHandler(stream=sys.stdout)
fmt = colorlog.ColoredFormatter(
"%(white)s%(asctime)s%(reset)s | %(log_color)s%(levelname)s%(reset)s | \
%(blue)s%(filename)s:%(lineno)s%(reset)s >>> %(log_color)s%(message)s%(reset)s")
stdout.setFormatter(fmt)
logger.addHandler(stdout)
logger.setLevel(arguments.log_level)

def log(text: str) -> None:
    """Log an info message to the console."""
    logging.info(text)

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
        max_tries : int = 5,
        ) -> requests.Response:
    """Get a URL.

    A simple wrapper to make a get request while providing our user agent, \
        and respecting rate limits.
    """
    if headers is None:
        headers = {}
    h = headers.copy()
    if "User-Agent" not in h:
        h["User-Agent"] = "FediFetcher (https://go.thms.uk/mgr)"

    if timeout == 0:
        timeout = arguments.http_timeout

    response = requests.get( url, headers= h, timeout=timeout)
    if response.status_code == Response.TOO_MANY_REQUESTS:
        if max_tries > 0:
            reset = parser.parse(response.headers["x-ratelimit-reset"])
            now = datetime.now(datetime.now(UTC).astimezone().tzinfo)
            wait = (reset - now).total_seconds() + 1
            log(f"Rate Limit hit requesting {url}. Waiting {wait} sec to retry at \
{response.headers['x-ratelimit-reset']}")
            time.sleep(wait)
            return get(url, headers, timeout, max_tries - 1)

        msg = f"Maximum number of retries exceeded for rate limited request {url}"
        raise requests.HTTPError(msg)
    return response
