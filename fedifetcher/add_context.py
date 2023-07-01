from datetime import datetime
import time

def add_context_url(url, server, access_token, helper):
    """add the given toot URL to the server"""
    search_url = f"https://{server}/api/v2/search?q={url}&resolve=true&limit=1"

    try:
        resp = helper.get(search_url, headers={
            "Authorization": f"Bearer {access_token}",
        })
    except Exception as ex:
        helper.log(
            f"Error adding url {search_url} to server {server}. Exception: {ex}"
        )
        return False

    if resp.status_code == helper.Response.OK:
        helper.log(f"Added context url {url}")
        return True
    elif resp.status_code == helper.Response.FORBIDDEN:
        helper.log(
            f"Error adding url {search_url} to server {server}. \
Status code: {resp.status_code}. "
            "Make sure you have the read:search scope enabled for your access token."
        )
        return False
    elif resp.status_code == helper.Response.TOO_MANY_REQUESTS:
        reset = datetime.strptime(resp.headers['x-ratelimit-reset'],
            '%Y-%m-%dT%H:%M:%S.%fZ')
        helper.log(f"Rate Limit hit when adding url {search_url}. Waiting to retry at \
{resp.headers['x-ratelimit-reset']}")
        time.sleep((reset - datetime.now()).total_seconds() + 1)
        return add_context_url(url, server, access_token, helper)
    else:
        helper.log(
            f"Error adding url {search_url} to server {server}. \
Status code: {resp.status_code}"
        )
        return False
