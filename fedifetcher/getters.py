"""Functions to get data from Fediverse servers."""
import logging
import re
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import requests
from dateutil import parser

from fedifetcher.ordered_set import OrderedSet

from . import api_lemmy, api_mastodon, helpers, parsers


def get_user_posts(
        user: dict[str, str],
        know_followings: OrderedSet,
        server: str,
) -> list[dict[str, str]] | None:
    """Get a list of posts from a user.

    Args:
    ----
    user (dict): The user to get the posts from.
    know_followings (set[str]): A set of known followings.
    server (str): The server to get the posts from.


    Returns:
    -------
    list[dict] | None: A list of posts from the user, or None if the user \
        couldn't be fetched.

    """
    parsed_url = parsers.user(user["url"])

    if (parsed_url is None) or (parsed_url[0] == server):
        know_followings.add(user["acct"])
        return None

    if re.match(r"^https:\/\/[^\/]+\/c\/", user["url"]):
        return api_lemmy.get_community_posts_from_url(parsed_url)

    if re.match(r"^https:\/\/[^\/]+\/u\/", user["url"]):
        return api_lemmy.get_user_posts_from_url(parsed_url)

    try:
        user_id = api_mastodon.get_user_id(parsed_url[1], parsed_url[0])
    except Exception as ex:
        logging.error(f"Error getting user ID for user {user['acct']}: {ex}")
        return None

    if not parsed_url[0] or not user_id:
        return None

    url = f"https://{parsed_url[0]}/api/v1/accounts/{user_id}/statuses?limit=40"
    response = helpers.get(url)

    if response.status_code == helpers.Response.OK:
        return response.json()

    if response.status_code == helpers.Response.NOT_FOUND:
        msg = f"User {user['acct']} was not found on server {parsed_url[0]}"
        logging.error(msg)
        raise Exception(msg)

    msg = f"Error getting URL {url} Status code: {response.status_code}"
    logging.exception(msg)
    return None


def get_toots(
        url : str,
        access_token : str,
        ) -> requests.Response:
    """Get toots from the specified URL.

    Args:
    ----
    url (str): The URL to get the toots from.
    access_token (str): The access token to use for authentication.


    Returns:
    -------
    requests.Response: The response from the server.


    Raises:
    ------
    Exception: If the access token is invalid.
    Exception: If the access token does not have the correct scope.
    Exception: If the server returns an unexpected status code.
    """
    response = helpers.get( url, headers={
        "Authorization": f"Bearer {access_token}",
    })

    if response.status_code == helpers.Response.OK:
        return response
    if response.status_code == helpers.Response.UNAUTHORIZED:
        msg = (
f"Error getting URL {url} Status code: {response.status_code}. \
It looks like your access token is incorrect.")
        raise Exception(
            msg,
        )
    if response.status_code == helpers.Response.FORBIDDEN:
        msg = (
f"Error getting URL {url} Status code: {response.status_code}. \
Make sure you have the read:statuses scope enabled for your access token.")
        raise Exception(
            msg,
        )
    msg = f"Error getting URL {url} Status code: {response.status_code}"
    raise Exception(
        msg,
    )

def get_reply_toots(
        user_id : str,
        server : str,
        access_token : str,
        seen_urls : OrderedSet,
        reply_since : datetime,
        ) -> Iterator[dict[str, Any]]:
    """Get replies by the user to other users since the given date.

    Args:
    ----
    user_id (str): The user ID to get the replies from.
    server (str): The server to get the replies from.
    access_token (str): The access token to use for authentication.
    seen_urls (set[str]): The URLs that have already been seen.
    reply_since (datetime): The date to look back to for replies.

    Returns:
    -------
    list[dict[str, Any]]: A list of toots.

    Raises:
    ------
    Exception: If the access token is invalid.
    Exception: If the access token does not have the correct scope.
    Exception: If the server returns an unexpected status code.
    """
    url = f"https://{server}/api/v1/accounts/{user_id}/statuses?exclude_replies=false&limit=40"

    try:
        resp = helpers.get(url, headers={
            "Authorization": f"Bearer {access_token}",
        })
    except Exception as ex:
        logging.error(
            f"Error getting replies for user {user_id} on server {server}: {ex}",
        )
        return iter([])

    if resp.status_code == helpers.Response.OK:
        toots = [
            toot
            for toot in resp.json()
            if toot["in_reply_to_id"]
            and toot["url"] not in seen_urls
            and datetime.strptime(
        toot["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ").astimezone(UTC) > reply_since
        ]
        for toot in toots:
            logging.info(f"Found reply toot: {toot['url']}")
        return iter(toots)
    if resp.status_code == helpers.Response.FORBIDDEN:
        msg = (
f"Error getting replies for user {user_id} on server {server}. \
Status code: {resp.status_code}. \
Make sure you have the read:statuses scope enabled for your access token.")
        raise Exception(
            msg,
        )

    msg = (
f"Error getting replies for user {user_id} on server {server}. \
Status code: {resp.status_code}")
    raise Exception(
        msg,
    )

def get_toot_context(  # noqa: PLR0911
        server : str,
        toot_id : str,
        toot_url : str,
        ) -> list[str]:
    """Get the URLs of the context toots of the given toot.

    Args:
    ----
    server (str): The server to get the context toots from.
    toot_id (str): The ID of the toot to get the context toots for.
    toot_url (str): The URL of the toot to get the context toots for.

    Returns:
    -------
    list[str]: The URLs of the context toots of the given toot.
    """
    try:
        if toot_url.find("/comment/") != -1:
            return get_comment_context(server, toot_id, toot_url)
        if toot_url.find("/post/") != -1:
            return get_comments_urls(server, toot_id, toot_url)
        url = f"https://{server}/api/v1/statuses/{toot_id}/context"
        try:
            resp = helpers.get(url)
        except Exception as ex:
            logging.error(f"Error getting context for toot {toot_url}. Exception: {ex}")
            return []

        if resp.status_code == helpers.Response.OK:
            try:
                res = resp.json()
            except Exception as ex:
                logging.error(
f"Error parsing context for toot {toot_url}. Exception: {ex}")
            else:
                logging.info(f"Got context for toot {toot_url}")
                return [toot["url"] for toot in (res["ancestors"] + res["descendants"])]
            return []
        if resp.status_code == helpers.Response.TOO_MANY_REQUESTS:
            reset = datetime.strptime(resp.headers["x-ratelimit-reset"],
                "%Y-%m-%dT%H:%M:%S.%fZ").astimezone(UTC)
            logging.warning(
f"Rate Limit hit when getting context for {toot_url}. \
Waiting to retry at {resp.headers['x-ratelimit-reset']}")
            time.sleep((reset - datetime.now(UTC)).total_seconds() + 1)
            return get_toot_context(server, toot_id, toot_url)
    except Exception as ex:
        logging.error(f"Error getting context for toot {toot_url}. Exception: {ex}")
    return []

def get_comment_context(
    server: str,
    toot_id: str,
    toot_url: str,
) -> list[str]:
    """Get the URLs of the context toots of the given toot.

    Args:
    ----
    server (str): The server to get the context toots from.
    toot_id (str): The ID of the toot to get the context toots for.
    toot_url (str): The URL of the toot to get the context toots for.

    Returns:
    -------
    list[str]: The URLs of the context toots of the given toot.
    """
    comment = f"https://{server}/api/v3/comment?id={toot_id}"
    try:
        resp = helpers.get(comment)
    except Exception as ex:
        logging.error(
f"Error getting comment {toot_id} from {toot_url}. Exception: {ex}")
        return []
    if resp.status_code == helpers.Response.OK:
        try:
            res = resp.json()
            post_id = res["comment_view"]["comment"]["post_id"]
            return get_comments_urls(server, post_id, toot_url)
        except Exception as ex:
            logging.error(
f"Error parsing context for comment {toot_url}. Exception: {ex}")
        return []
    if resp.status_code == helpers.Response.TOO_MANY_REQUESTS:
        reset = datetime.strptime(resp.headers["x-ratelimit-reset"],
            "%Y-%m-%dT%H:%M:%S.%fZ").astimezone(UTC)
        logging.warning(
f"Rate Limit hit when getting context for {toot_url}. \
Waiting to retry at {resp.headers['x-ratelimit-reset']}")
        time.sleep((reset - datetime.now(UTC)).total_seconds() + 1)
        return get_comment_context(server, toot_id, toot_url)

    return []

def get_comments_urls(  # noqa: PLR0912
        server : str,
        post_id : str,
        toot_url : str,
        ) -> list[str]:
    """Get the URLs of the comments of the given post.

    Args:
    ----
    server (str): The server to get the comments from.
    post_id (str): The ID of the post to get the comments for.
    toot_url (str): The URL of the post to get the comments for.

    Returns:
    -------
    list[str]: The URLs of the comments of the given post.
    """
    urls = []
    url = f"https://{server}/api/v3/post?id={post_id}"
    try:
        resp = helpers.get(url)
    except Exception as ex:
        logging.error(f"Error getting post {post_id} from {toot_url}. Exception: {ex}")
        return []

    if resp.status_code == helpers.Response.OK:
        try:
            res = resp.json()
            if res["post_view"]["counts"]["comments"] == 0:
                return []
            urls.append(res["post_view"]["post"]["ap_id"])
        except Exception as ex:
            logging.error(f"Error parsing post {post_id} from {toot_url}. \
                        Exception: {ex}")

    url = f"https://{server}/api/v3/comment/list?post_id={post_id}&sort=New&limit=50"
    try:
        resp = helpers.get(url)
    except Exception as ex:
        logging.error(f"Error getting comments for post {post_id} from {toot_url}. \
Exception: {ex}")
        return []

    if resp.status_code == helpers.Response.OK:
        try:
            res = resp.json()
            list_of_urls = \
                [comment_info["comment"]["ap_id"] for comment_info in res["comments"]]
            logging.info(f"Got {len(list_of_urls)} comments for post {toot_url}")
            urls.extend(list_of_urls)
        except Exception as ex:
            logging.error(
f"Error parsing comments for post {toot_url}. Exception: {ex}")
        else:
            return urls
    elif resp.status_code == helpers.Response.TOO_MANY_REQUESTS:
        reset = datetime.strptime(resp.headers["x-ratelimit-reset"],
            "%Y-%m-%dT%H:%M:%S.%fZ").astimezone(UTC)
        logging.info(f"Rate Limit hit when getting comments for {toot_url}. Waiting to \
                    retry at {resp.headers['x-ratelimit-reset']}")
        time.sleep((reset - datetime.now(UTC)).total_seconds() + 1)
        return get_comments_urls(server, post_id, toot_url)

    logging.error(
f"Error getting comments for post {toot_url}. Status code: {resp.status_code}")
    return []

def get_paginated_mastodon(
        url : str,
        limit : int = 40,
        headers : dict[str, str] | None = None,
        timeout : int = 10,
        max_tries : int = 3,
        ) -> list[dict[str, Any]]:
    """Make a paginated request to mastodon.

    Args:
    ----
    url (str): The URL to make the request to.
    limit (int | str, optional): The number of items to get per request. Defaults to 40.
    headers (dict[str, str], optional): The headers to use for the request. \
        Defaults to {}.
    timeout (int, optional): The timeout for the request. Defaults to 10.
    max_tries (int, optional): The maximum number of times to retry the request. \
        Defaults to 3.

    Raises:
    ------
    Exception: If the request fails.
    """
    if headers is None:
        headers = {}
    furl = f"{url}?limit={limit}" if isinstance(limit, int) else url

    response = helpers.get(furl, headers, timeout, max_tries)

    if response.status_code != helpers.Response.OK:
        if response.status_code == helpers.Response.UNAUTHORIZED:
            msg = (
f"Error getting URL {url} Status code: {response.status_code}. \
Ensure your access token is correct")
            raise Exception(
                msg,
            )
        if response.status_code == helpers.Response.FORBIDDEN:
            msg = (
f"Error getting URL {url} Status code: {response.status_code}. \
Make sure you have the correct scopes enabled for your access token.")
            raise Exception(
                msg,
            )
        msg = (f"Error getting URL {url} Status code: {response.status_code}")
        raise Exception(
            msg,
        )

    result = response.json()

    if(isinstance(limit, int)):
        while len(result) < limit and "next" in response.links:
            response = helpers.get(
                response.links["next"]["url"], headers, timeout, max_tries)
            result = result + response.json()
    else:
        while parser.parse(result[-1]["created_at"]) >= limit \
                and "next" in response.links:
            response = helpers.get(
                response.links["next"]["url"], headers, timeout, max_tries)
            result = result + response.json()

    return result
