"""Helper functions for fedifetcher."""
import time
from datetime import datetime

import requests
from dateutil import parser

from .argparser import arguments


class Response:
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

def get(url, headers = {}, timeout = 0, max_tries = 5):
    """A simple wrapper to make a get request while providing our user agent, \
    and respecting rate limits.
    """
    h = headers.copy()
    if "User-Agent" not in h:
        h["User-Agent"] = "FediFetcher (https://go.thms.uk/mgr)"

    if timeout == 0:
        timeout = arguments.http_timeout

    response = requests.get( url, headers= h, timeout=timeout)
    if response.status_code == Response.TOO_MANY_REQUESTS:
        if max_tries > 0:
            reset = parser.parse(response.headers["x-ratelimit-reset"])
            now = datetime.now(datetime.now().astimezone().tzinfo)
            wait = (reset - now).total_seconds() + 1
            log(f"Rate Limit hit requesting {url}. Waiting {wait} sec to retry at \
{response.headers['x-ratelimit-reset']}")
            time.sleep(wait)
            return get(url, headers, timeout, max_tries - 1)

        msg = f"Maximum number of retries exceeded for rate limited request {url}"
        raise Exception(msg)
    return response

def log(text):
    print(f"{datetime.now()} {datetime.now().astimezone().tzinfo}: {text}")
