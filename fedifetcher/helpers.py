from datetime import datetime
from dateutil import parser
import time
import requests

def get(url, headers = {}, timeout = 0, max_tries = 5):
    """A simple wrapper to make a get request while providing our user agent, \
        and respecting rate limits"""
    h = headers.copy()
    if 'User-Agent' not in h:
        h['User-Agent'] = 'FediFetcher (https://go.thms.uk/mgr)'

    if timeout == 0:
        timeout = arguments.http_timeout

    response = requests.get( url, headers= h, timeout=timeout)
    if response.status_code == Response.TOO_MANY_REQUESTS:
        if max_tries > 0:
            reset = parser.parse(response.headers['x-ratelimit-reset'])
            now = datetime.now(datetime.now().astimezone().tzinfo)
            wait = (reset - now).total_seconds() + 1
            log(f"Rate Limit hit requesting {url}. Waiting {wait} sec to retry at \
{response.headers['x-ratelimit-reset']}")
            time.sleep(wait)
            return get(url, headers, timeout, max_tries - 1)

        raise Exception(f"Maximum number of retries exceeded for rate limited request \
{url}")
    return response

def log(text):
    print(f"{datetime.now()} {datetime.now().astimezone().tzinfo}: {text}")
