"""Add context toots to the server."""
import time
from datetime import UTC, datetime

import requests

from fedifetcher import parsers
from fedifetcher.ordered_set import OrderedSet

from . import getters, helpers


def add_context_url(
        url : str,
        server : str,
        access_token : str,
        ) -> bool:
    """Add the given toot URL to the server.

    Args:
    ----
    url: The URL of the toot to add.
    server: The server to add the toot to.
    access_token: The access token to use to add the toot.

    Returns:
    -------
    bool: True if the toot was added successfully, False otherwise.
    """
    search_url = f"https://{server}/api/v2/search?q={url}&resolve=true&limit=1"

    try:
        resp = helpers.get(search_url, headers={
            "Authorization": f"Bearer {access_token}",
        })
    except requests.HTTPError as ex:
        helpers.log(
            f"Error adding url {search_url} to server {server}. Exception: {ex}",
        )
        return False

    if resp.status_code == helpers.Response.OK:
        helpers.log(f"Added context url {url}")
        return True
    if resp.status_code == helpers.Response.FORBIDDEN:
        helpers.log(
            f"Error adding url {search_url} to server {server}. \
Status code: {resp.status_code}. "
            "Make sure you have the read:search scope enabled for your access token.",
        )
        return False
    if resp.status_code == helpers.Response.TOO_MANY_REQUESTS:
        reset = datetime.strptime(resp.headers["x-ratelimit-reset"],
            "%Y-%m-%dT%H:%M:%S.%fZ").astimezone()
        helpers.log(f"Rate Limit hit when adding url {search_url}. Waiting to retry at \
{resp.headers['x-ratelimit-reset']}")
        time.sleep((reset - datetime.now(UTC)).total_seconds() + 1)
        return add_context_url(url, server, access_token)
    helpers.log(
        f"Error adding url {search_url} to server {server}. \
Status code: {resp.status_code}",
    )
    return False

def add_user_posts(  # noqa: PLR0913
        server : str,
        access_token : str,
        followings : list,
        know_followings : set,
        all_known_users : set,
        seen_urls : set,
        ) -> None:
    """Add the given user's posts to the server.

    Args:
    ----
    server: The server to add the posts to.
    access_token: The access token to use to add the posts.
    followings: The list of users to add the posts of.
    know_followings: The list of users whose posts we already know.
    all_known_users: The list of all users whose posts we already know.
    seen_urls: The list of all URLs we have already seen.
    """
    for user in followings:
        if user["acct"] not in all_known_users and not user["url"].startswith(f"https://{server}/"):
            posts = getters.get_user_posts(user, know_followings, server)

            if(posts is not None):
                count = 0
                failed = 0
                for post in posts:
                    if post.get("reblog") is None and post.get("url") and \
                            post.get("url") not in seen_urls:
                        added = add_post_with_context(
                            post, server, access_token, seen_urls)
                        if added is True:
                            seen_urls.add(post["url"])
                            count += 1
                        else:
                            failed += 1
                helpers.log(
                    f"Added {count} posts for user {user['acct']} with {failed} errors")
                if failed == 0:
                    know_followings.add(user["acct"])
                    all_known_users.add(user["acct"])

def add_post_with_context(
        post : dict,
        server : str,
        access_token : str,
        seen_urls : set,
        ) -> bool:
    """Add the given post to the server.

    Args:
    ----
    post: The post to add.
    server: The server to add the post to.
    access_token: The access token to use to add the post.
    seen_urls: The list of all URLs we have already seen.

    Returns:
    -------
    bool: True if the post was added successfully, False otherwise.
    """
    added = add_context_url(post["url"], server, access_token)
    if added is True:
        seen_urls.add(post["url"])
        if ("replies_count" in post or "in_reply_to_id" in post) and getattr(
                helpers.arguments, "backfill_with_context", 0) > 0:
            parsed_urls : dict[str, tuple[str, str | None]] = {}
            parsed = parsers.post(post["url"], parsed_urls)
            if parsed is None:
                return True
            known_context_urls = getters.get_all_known_context_urls(
                server, [post], parsed_urls)
            add_context_urls(server, access_token, known_context_urls, seen_urls)
        return True

    return False

def add_context_urls(
        server : str,
        access_token : str,
        context_urls : filter[str],
        seen_urls : OrderedSet,
        ) -> None:
    """Add the given toot URLs to the server.

    Args:
    ----
    server: The server to add the toots to.
    access_token: The access token to use to add the toots.
    context_urls: The list of toot URLs to add.
    seen_urls: The list of all URLs we have already seen.
    """
    count = 0
    failed = 0
    for url in context_urls:
        if url not in seen_urls:
            added = add_context_url(url, server, access_token)
            if added is True:
                seen_urls.add(url)
                count += 1
            else:
                failed += 1

    helpers.log(f"Added {count} new context toots (with {failed} failures)")
