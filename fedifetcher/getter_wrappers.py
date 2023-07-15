"""Functions to get data from Fediverse servers."""
import itertools
import json
import logging
from collections.abc import Iterable, Iterator
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


def get_notification_users(
        server : str,
        access_token : str,
        known_users : OrderedSet,
        max_age : int = 24,
        ) -> list[str]:
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
    notifications = api_mastodon.get_notifications(
        server,
        access_token,
        int(since.timestamp()),
    )
    notification_users = []
    for notification in notifications:
        notification_date : datetime = cast(datetime, notification["created_at"])
        if(notification_date >= since and notification["account"] not in \
                notification_users):
            notification_users.append(notification["account"])

    new_notification_users = filter_known_users(notification_users, known_users)

    logging.info(
f"Found {len(notification_users)} users in notifications, \
{len(new_notification_users)} of which are new")

    return [user["account"] for user in filter_known_users(
                                            notification_users, known_users)]

def get_new_follow_requests(
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
    follow_requests = list(api_mastodon.get_follow_requests(
        server,
        access_token,
        limit,
    ))

    # Remove any we already know about
    new_follow_requests = filter_known_users(
        follow_requests, known_followings)

    logging.info(f"Got {len(follow_requests)} follow_requests, \
{len(new_follow_requests)} of which are new")

    return new_follow_requests

def get_new_followers(
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
    followers = list(api_mastodon.get_followers(server, token, user_id, limit))

    # Remove any we already know about
    new_followers = filter_known_users(
        followers, known_followers)

    logging.info(
f"Got {len(followers)} followers, {len(new_followers)} of which are new")

    return new_followers

def get_new_followings(
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
    following = list(api_mastodon.get_following(server, token, user_id, limit))

    # Remove any we already know about
    new_followings = filter_known_users(
        list(following), known_followings)

    logging.info(
f"Got {len(following)} followings, {len(new_followings)} of which are new")

    return new_followings

def get_all_reply_toots(
    server: str,
    user_ids: Iterable[str],
    access_token: str,
    seen_urls: OrderedSet,
    reply_interval_hours: int,
) -> Iterator[dict[str, Any]]:
    """Get all replies to other users by the given users in the last day.

    Args:
    ----
    server (str): The server to get the toots from.
    user_ids (Iterable[str]): The user IDs to get the toots from.
    access_token (str): The access token to use for authentication.
    seen_urls (OrderedSet[str]): The URLs that have already been seen.
    reply_interval_hours (int): The number of hours to look back for replies.

    Yields:
    ------
    dict[str, Any]: A toot.

    Raises:
    ------
    Exception: If the access token is invalid.
    Exception: If the access token does not have the correct scope.
    Exception: If the server returns an unexpected status code.
    """
    replies_since = datetime.now(UTC) - timedelta(hours=reply_interval_hours)
    for user_id in user_ids:
        replies = api_mastodon.get_reply_posts_from_id(
            user_id,
            server,
            access_token,
            seen_urls,
            replies_since,
        )
        if replies is not None:
            yield from replies


def get_all_known_context_urls(  # noqa: C901, PLR0912
    server: str,
    reply_toots: Iterator[dict[str, str]] | list[dict[str, str]],
    parsed_urls: dict[str, tuple[str | None, str | None]],
    external_tokens: dict[str, str],
    pgupdater: PostgreSQLUpdater,
    home_server_token: str,
    status_id_cache: dict[str, str],
) -> Iterable[str]:
    """Get the context toots of the given toots from their original server.

    Args:
    ----
    server (str): The home server of the user.
    reply_toots (Iterator[Optional[Dict[str, Optional[str]]]]): \
        The toots to get the context toots for.
    parsed_urls (Dict[str, Optional[Tuple[str, str]]]): \
        The parsed URL of the toots.

    Returns:
    -------
    filter[str]: The URLs of the context toots.

    Raises:
    ------
    Exception: If the server returns an unexpected status code.
    """
    known_context_urls = []

    if reply_toots is not None:
        for toot in reply_toots:
            if toot is not None and toot_has_parseable_url(toot, parsed_urls):
                reblog = toot.get("reblog")
                if isinstance(reblog, str):
                    try:
                        reblog_dict = json.loads(reblog)
                        url = reblog_dict.get("url")
                        if url is None:
                            logging.error("Error accessing URL in the boosted toot")
                            continue
                        logging.debug(f"Got boosted toot URL {url}")
                    except json.JSONDecodeError:
                        logging.error("Error decoding JSON in the boosted toot")
                        continue
                elif isinstance(reblog, dict):
                    url = reblog.get("url")
                    if url is None:
                        logging.error("Error accessing URL in the boosted toot")
                        continue
                    logging.debug(f"Got boosted toot URL {url}")
                elif toot.get("url") is not None:
                    url = str(toot["url"])
                else:
                    logging.error("Error accessing URL in the toot")
                    continue

                parsed_url = parsers.post(url, parsed_urls)
                if parsed_url and parsed_url[0] and parsed_url[1]:
                    try:
                        context = get_post_context(parsed_url[0], parsed_url[1], url,
                                                external_tokens, pgupdater, server,
                                                home_server_token, status_id_cache)
                    except Exception as ex:
                        logging.error(f"Error getting context for toot {url} : {ex}")
                        logging.debug(
                            f"Debug info: {parsed_url[0]}, {parsed_url[1]}, {url}")
                        continue
                    if context:
                        logging.info(f"Got {len(context)} context posts for {url}")
                        known_context_urls.extend(context)

    return filter(
        lambda url: not url.startswith(f"https://{server}/"), known_context_urls)



def get_all_replied_toot_server_ids(
    server: str,
    reply_toots: Iterator[dict[str, Any]],
    replied_toot_server_ids: dict[str, str | None],
    parsed_urls: dict[str, tuple[str | None, str | None]],
) -> Iterable[tuple[str | None, str | None]]:
    """Get the server and ID of the toots the given toots replied to.

    Args:
    ----
    server (str): The server to get the replied toots from.
    reply_toots (Iterator[dict[str, Any]]): The toots to get the replied toots for.
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
            "User-Agent": "FediFetcher (https://go.thms.uk/mgr)",
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

def get_all_context_urls(
    server: str,
    replied_toot_ids: Iterable[tuple[str | None, str | None]],
    external_tokens: dict[str, str],
    pgupdater: PostgreSQLUpdater,
    home_server: str,
    home_server_token: str,
    status_id_cache: dict[str, str],
) -> Iterable[str]:
    """Get the URLs of the context toots of the given toots.

    Args:
    ----
    server (str): The server to get the context toots from.
    replied_toot_ids (filter[tuple[str | None, str | None]]): The server and ID of the \
        toots to get the context toots for.

    Returns:
    -------
    filter[str]: The URLs of the context toots of the given toots.
    """
    return cast(Iterable[str], filter(
        lambda url: not str(url).startswith(f"https://{server}/"),
        itertools.chain.from_iterable(
            get_post_context(server, toot_id, url, external_tokens, pgupdater,
                                home_server, home_server_token, status_id_cache)
            for (url, (s, toot_id)) in cast(Iterable[tuple[str, str]], replied_toot_ids)
        ),
    ))


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
