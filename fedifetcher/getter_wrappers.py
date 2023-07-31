"""Functions to get data from Fediverse servers."""
import asyncio
import itertools
import json
import logging
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import requests

from fedifetcher import api_mastodon
from fedifetcher.getters import (
    get_post_context,
)
from fedifetcher.ordered_set import OrderedSet
from fedifetcher.postgresql import PostgreSQLUpdater

from . import helpers, parsers


async def get_notification_users(
        server : str,
        access_token : str,
        known_users : OrderedSet,
        max_age : int = 24,
        ) -> list[dict[str, str]]:
    """Get a list of users that have interacted with the user in last `max_age` hours.

    Args:
    ----
    server (str): The server to get the notifications from.
    access_token (str): The access token to use for authentication.
    known_users (list[str]): A list of known users.
    max_age (int, optional): The maximum age of the notifications to consider. \
        Defaults to 24.

    Returns:
    -------
    list[str]: A list of users that have interacted with the user in the last \
        `max_age` hours.

    """
    since = datetime.now(
        datetime.now(UTC).astimezone().tzinfo) - timedelta(hours=max_age)
    notifications = await api_mastodon.Mastodon(server,
        access_token).get_notifications(since_id=str(int(since.timestamp())))
    notification_users = []
    for notification in notifications:
        created_at = notification["created_at"]
        notification_date : datetime = datetime.strptime(
            created_at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
        if(notification_date >= since and notification["account"] not in \
                notification_users):
            notification_users.append(notification["account"])

    new_notification_users = filter_known_users(notification_users, known_users)

    logging.info(
f"Found {len(notification_users)} users in notifications, \
{len(new_notification_users)} of which are new")

    # return [user.get("account") for user in filter_known_users(
    #                                         notification_users, known_users)]
    users: list[dict[str, str]] = []
    for user in filter_known_users(notification_users, known_users):
        account = user.get("acct")
        if account is not None:
            users.append(user)

    return users

async def get_new_follow_requests(
        server : str,
        access_token : str,
        limit : int, # = 40,
        known_followings : OrderedSet,
        ) -> list[dict]:
    """Get any new follow requests for the specified user.

    Args:
    ----
    server (str): The server to get the follow requests from.
    access_token (str): The access token to use for authentication.
    limit (int): The maximum number of follow requests to get.
    known_followings (set[str]): A set of known followings.


    Returns:
    -------
    list[dict]: A list of follow requests.
    """
    follow_requests = list(await api_mastodon.Mastodon(server,
        access_token).get_follow_requests(limit=limit))

    # Remove any we already know about
    new_follow_requests = filter_known_users(
        follow_requests, known_followings)

    logging.info(f"Got {len(follow_requests)} follow_requests, \
{len(new_follow_requests)} of which are new")

    return new_follow_requests

async def get_new_followers(
        server : str,
        token: str | None,
        user_id : str,
        limit : int, # = 40,
        known_followers : OrderedSet,
        ) -> list[dict]:
    """Get any new followings for the specified user, up to the max number provided.

    Args:
    ----
    server (str): The server to get the followers from.
    token (str): The access token to use for authentication.
    user_id (str): The ID of the user to get the followers for.
    limit (int): The maximum number of followers to get.
    known_followers (set[str]): A set of known followers.



    Returns:
    -------
    list[dict]: A list of followers.
    """
    followers = list(await api_mastodon.Mastodon(
        server, token).get_followers(user_id, limit))

    # Remove any we already know about
    new_followers = filter_known_users(
        followers, known_followers)

    logging.info(
f"Got {len(followers)} followers, {len(new_followers)} of which are new")

    return new_followers

async def get_new_followings(
        server : str,
        token: str | None,
        user_id : str,
        limit : int, # = 40,
        known_followings : OrderedSet,
        ) -> list[dict]:
    """Get any new followings for the specified user, up to the max number provided.

    Args:
    ----
    server (str): The server to get the followings from.
    token (str): The access token to use for authentication.
    user_id (str): The ID of the user to get the followings for.
    limit (int): The maximum number of followings to get.
    known_followings (set[str]): A set of known followings.


    Returns:
    -------
    list[dict]: A list of followings.
    """
    following = list(await api_mastodon.Mastodon(server, token).get_following(
        user_id, limit))

    # Remove any we already know about
    new_followings = filter_known_users(
        list(following), known_followings)

    logging.info(
f"Got {len(following)} followings, {len(new_followings)} of which are new")

    return new_followings

async def get_all_reply_toots(
    server: str,
    user_ids: Iterable[str],
    access_token: str,
    pgupdater: PostgreSQLUpdater,
    reply_interval_hours: int,
) -> list[dict[str, Any]]:
    """Get all replies to other users by the given users in the last day.

    Args:
    ----
    server (str): The server to get the toots from.
    user_ids (Iterable[str]): The user IDs to get the toots from.
    access_token (str): The access token to use for authentication.
    pgupdater (PostgreSQLUpdater): The PostgreSQL updater.
    reply_interval_hours (int): The number of hours to look back for replies.

    Returns:
    -------
    list[dict[str, Any]]: A list of toots.

    Raises:
    ------
    Exception: If the access token is invalid.
    Exception: If the access token does not have the correct scope.
    Exception: If the server returns an unexpected status code.
    """
    replies_since = datetime.now(UTC) - timedelta(hours=reply_interval_hours)
    all_replies = []
    for user_id in user_ids:
        replies = await api_mastodon.Mastodon(server,
            access_token, pgupdater).get_reply_posts_from_id(
            user_id,
            replies_since,
        )
        if replies is not None:
            all_replies.extend(replies)
    return all_replies


async def get_all_known_context_urls(
    home_server: str,
    reply_toots: list[dict[str, str]],
    parsed_urls: dict[str, tuple[str | None, str | None]],
    external_tokens: dict[str, str],
    pgupdater: PostgreSQLUpdater,
    home_server_token: str,
) -> Iterable[str]:
    known_context_urls = []
    if reply_toots is not None:
        toots_to_get_context_for: list[tuple[tuple[str, str], str]] = []
        for toot in reply_toots:
            context = _get_context_url(toot, parsed_urls)
            if context:
                toots_to_get_context_for.append(context)
        # Get the context for the toots
        tasks = [
            asyncio.ensure_future(get_post_context(
                x[0][0],
                x[0][1],
                x[1],
                external_tokens,
                pgupdater,
                home_server,
                home_server_token,
            ))
            for x in toots_to_get_context_for
        ]
        results = await asyncio.gather(*tasks)
        for post in results:
            if post:
                known_context_urls.extend(post)
        toots_to_get_context_for_by_server: dict[
            str, list[tuple[tuple[str, str], str]]] = {}

        for post in toots_to_get_context_for:
            parsed_url = post[0]
            if parsed_url[0] not in toots_to_get_context_for_by_server:
                toots_to_get_context_for_by_server[parsed_url[0]] = []
            toots_to_get_context_for_by_server[parsed_url[0]].append(post)
        server_tasks = []
        for server in toots_to_get_context_for_by_server:
            server_tasks.append(
                asyncio.ensure_future(get_context_for_server(
                    server,
                    external_tokens,
                    pgupdater,
                    home_server,
                    home_server_token,
                    toots_to_get_context_for_by_server[server],
                )),
            )
        results = await asyncio.gather(*server_tasks)
        for result in results:
            if result:
                known_context_urls.extend(result)

    return known_context_urls

async def get_context_for_server(server : str,  # noqa: ARG001
            external_tokens : dict[str, str],
            pgupdater : PostgreSQLUpdater,
            home_server : str,
            home_server_token : str,
            toots_to_get_context_for : list[tuple[tuple[str, str], str]],
            ) -> list[str]:
    """Get the context for the given toots from their original server."""
    known_context_urls = []
    for post in toots_to_get_context_for:
        parsed_url = post[0]
        url = post[1]
        try:
            context = await get_post_context(
                    parsed_url[0],
                    parsed_url[1],
                    url,
                    external_tokens,
                    pgupdater,
                    home_server,
                    home_server_token,
                )
        except Exception as ex:
            logging.error(f"Error getting context for toot {url} : {ex}")
            logging.debug(
                    f"Debug info: {parsed_url[0]}, {parsed_url[1]}, {url}")
            continue
        if context:
            logging.info(f"Got {len(context)} context posts for {url}")
            known_context_urls.extend(context)
    return known_context_urls

def _get_context_url(toot : dict[str, str],
                parsed_urls : dict[str, tuple[str | None, str | None]],
                ) -> tuple | None:
    if toot is not None and toot_has_parseable_url(toot, parsed_urls):
        reblog = toot.get("reblog")
        if isinstance(reblog, str):
            try:
                reblog_dict = json.loads(reblog)
                url = reblog_dict.get("url")
                if url is None:
                    logging.error("Error accessing URL in the boosted toot")
                    return None
                logging.debug(f"Got boosted toot URL {url}")
            except json.JSONDecodeError:
                logging.error("Error decoding JSON in the boosted toot")
                return None
        elif isinstance(reblog, dict):
            url = reblog.get("url")
            if url is None:
                logging.error("Error accessing URL in the boosted toot")
                return None
            logging.debug(f"Got boosted toot URL {url}")
        elif toot.get("url") is not None:
            url = str(toot["url"])
        else:
            logging.error("Error accessing URL in the toot")
            return None

        parsed_url = parsers.post(url, parsed_urls)
        if parsed_url and parsed_url[0] and parsed_url[1]:
            return (parsed_url, url)
    logging.error("Error parsing URL in the toot")
    return None


def get_all_replied_toot_server_ids(
    server: str,
    reply_toots: list[dict[str, Any]],
    replied_toot_server_ids: dict[str, str | None],
    parsed_urls: dict[str, tuple[str | None, str | None]],
) -> Iterable[tuple[str | None, str | None]]:
    """Get the server and ID of the toots the given toots replied to.

    Args:
    ----
    server (str): The server to get the replied toots from.
    reply_toots (list[dict[str, Any]]): The toots to get the replied toots for.
    replied_toot_server_ids (dict[str, str | None]): The server and ID of the toots \
        that have already been replied to.
    parsed_urls (dict[str, dict[str, str] | None]): The parsed URLs of the toots.

    Returns:
    -------
    filter[str | tuple[str, tuple[str, str]] | None]: The server and ID of the toots \
        the given toots replied to.
    """
    return filter(
        lambda replied_to: replied_to is not None,
        (get_replied_toot_server_id(
                server,
                toot,
                replied_toot_server_ids,
                parsed_urls,
            ) for toot in reply_toots),
    )

def get_replied_toot_server_id(  # noqa: PLR0911
    server: str,
    toot: dict[str, Any],
    replied_toot_server_ids: dict[str, str | None],
    parsed_urls: dict[str, tuple[str | None, str | None]],
) -> tuple[str | None, str | None]:
    """Get the server and ID of the toot the given toot replied to."""
    logging.debug(f"Getting replied post's server and ID for post {toot['id']}")
    in_reply_to_id = toot["in_reply_to_id"]
    in_reply_to_account_id = toot["in_reply_to_account_id"]
    mentions = [
        mention
        for mention in toot["mentions"]
        if mention["id"] == in_reply_to_account_id
    ]
    if len(mentions) < 1:
        logging.info(f"Could not find mention for post {in_reply_to_id}")
        return (None, None)

    mention = mentions[0]

    o_url = f"https://{server}/@{mention['acct']}/{in_reply_to_id}"
    if o_url in replied_toot_server_ids:
        if replied_toot_server_ids[o_url] is None:
            logging.debug(f"Found {o_url} in replied toots dictionary as None")
            return (None, None)
        if isinstance(replied_toot_server_ids[o_url], str):
            found_server, found_id = cast(
                str, replied_toot_server_ids[o_url]).split(",")
            logging.debug(
        f"Found {o_url} in replied toots dictionary as {found_server}, {found_id}")
            return (
                found_server,
                found_id,
                    )

    url = get_redirect_url(o_url)

    if url is None:
        logging.error(f"Error getting redirect URL for URL {o_url}")
        return (None, None)

    match = parsers.post(url, parsed_urls)
    if match:
        if match[0] is not None and match[1] is not None:
            logging.debug(
                f"Added {url} to replied toots dictionary as {match[0]}, {match[1]}")
            replied_toot_server_ids[o_url] = f"{url},{match[0]},{match[1]}"
            return (match[0], match[1])
        logging.debug(f"Added {url} to replied toots dictionary as None")
        replied_toot_server_ids[o_url] = None
        return (None, None)

    logging.error(f"Error parsing toot URL {url}")
    replied_toot_server_ids[o_url] = None
    return (None, None)


def get_redirect_url(url : str) -> str | None:
    """Get the URL given URL redirects to.

    Args:
    ----
    url (str): The URL to get the redirect URL for.

    Returns:
    -------
    str | None: The URL the given URL redirects to, or None if the URL does not \
        redirect.
    """
    try:
        resp = requests.head(url, allow_redirects=False, timeout=5,headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 +https://github.com/Teqed Meowstodon/1.0.0",  # noqa: E501
        })
    except Exception as ex:
        logging.error(f"Error getting redirect URL for URL {url} Exception: {ex}")
        return None

    if resp.status_code == helpers.Response.OK:
        return url
    if resp.status_code == helpers.Response.FOUND:
        redirect_url = resp.headers["Location"]
        logging.debug(f"Discovered redirect for URL {url}")
        return redirect_url
    logging.error(
        f"Error getting redirect URL for URL {url} Status code: {resp.status_code}",
    )
    return None

async def get_all_context_urls(  # noqa: PLR0913
        server: str,
        replied_toot_ids: Iterable[tuple[str | None, str | None]],
        external_tokens: dict[str, str],
        pgupdater: PostgreSQLUpdater,
        home_server: str,
        home_server_token: str,
) -> Iterable[str]:
    """Get the URLs of the context toots of the given toots.

    Args:
    ----
    server (str): The server to get the context toots from.
    replied_toot_ids (Iterable[tuple[str | None, str | None]]): The server and ID of \
        the toots to get the context toots for.
    external_tokens (dict[str, str]): The access tokens for external servers.
    pgupdater (PostgreSQLUpdater): The PostgreSQL updater.
    home_server (str): The home server.
    home_server_token (str): The access token for the home server.

    Returns:
    -------
    Iterable[str]: The URLs of the context toots of the given toots.
    """
    # Filter replied toots that have a server and ID
    _replied_toot_ids: Iterable[tuple[str, str]] = [
        (url, toot_id)
        for url, toot_id in replied_toot_ids
        if url is not None and toot_id is not None
    ]
    # Sort the replied toots by server
    _replied_toot_ids = sorted(_replied_toot_ids, key=lambda x: x[0])
    # Sort them into a dictionary with a key for each server
    __replied_toot_ids = {
        server: list(toots)
        for server, toots in itertools.groupby(_replied_toot_ids, key=lambda x: x[0])
    }
    # For each toot tuple, add it to a tuple of itself and the server it is on
    ___replied_toot_ids: dict[str, list[tuple[tuple[str, str], str]]] = {}
    for server in __replied_toot_ids:
        ___replied_toot_ids[server] = [
            (toot, server)
            for toot in __replied_toot_ids[server]
        ]

    context_urls = []
    promises = []
    for server in __replied_toot_ids:
        promises.append(
            asyncio.ensure_future(get_context_for_server(
                server,
                external_tokens,
                pgupdater,
                home_server,
                home_server_token,
                ___replied_toot_ids[server],
            )),
        )
    results = await asyncio.gather(*promises)
    for result in results:
        if result:
            context_urls.extend(result)
    # Filter out duplicate URLs and self-references
    return [
        url for url in context_urls
        if not str(url).startswith(f"https://{server}/") and url != server
    ]



def filter_known_users(
        users : list[dict[str, str]],
        known_users : OrderedSet,
        ) -> list[dict[str, str]]:
    """Filter out users that are already known.

    Args:
    ----
    users (list[dict[str, str]]): The users to filter.
    known_users (list[str]): The users that are already known.

    Returns:
    -------
    list[dict[str, str]]: The users that are not already known.
    """
    return list(filter(
        lambda user: user["acct"] not in known_users,
        users,
    ))

def toot_has_parseable_url(
    toot: dict[str, Any],
    parsed_urls: dict[str, tuple[str | None, str | None]],
) -> bool:
    """Check if the given toot has a parseable URL.

    Args:
    ----
    toot (dict[str, Any]): The toot to check.
    parsed_urls (dict[str, tuple[str, str] | None]): \
        The URLs that have already been parsed.

    Returns:
    -------
    bool: True if the toot has a parseable URL, False otherwise.
    """
    url = toot["url"] if toot["reblog"] is None else toot["reblog"]["url"]
    parsed = parsers.post(url, parsed_urls)
    return parsed is not None
