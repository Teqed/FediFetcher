"""Mastodon API functions."""
import functools
import inspect
import logging
from collections.abc import Callable, Generator, Iterable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

import requests
from mastodon import (
    Mastodon,
    MastodonAPIError,
    MastodonError,
    MastodonNotFoundError,
    MastodonRatelimitError,
    MastodonServiceUnavailableError,
    MastodonUnauthorizedError,
)

from fedifetcher.ordered_set import OrderedSet

from . import helpers

T = TypeVar("T")
def handle_mastodon_errors(
        default_return_value: T) -> Callable: # type: ignore # noqa: PGH003
    """Handle Mastodon errors."""
    def decorator(func: Callable[..., T | None]) -> Callable[..., T | None]:
        sig = inspect.signature(func)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T | None:  # noqa: ANN401
            bound = sig.bind(*args, **kwargs)

            server = bound.arguments.get("server", "Unknown")

            try:
                return func(*args, **kwargs)
            except MastodonNotFoundError:
                logging.error(
                    f"Error with Mastodon API on server {server}. Status code: 404. "
                    "Ensure the server is correct.",
                )
                return default_return_value
            except MastodonRatelimitError:
                logging.error(
                    f"Error with Mastodon API on server {server}. Status code: 429. "
                    "You are being rate limited. Try again later.",
                )
                return default_return_value
            except MastodonUnauthorizedError:
                logging.error(
                    f"Error with Mastodon API on server {server}. Status code: 401. "
                    "This endpoint requires an authentication token.",
                )
                return default_return_value
            except MastodonServiceUnavailableError:
                logging.error(
                    f"Error with Mastodon API on server {server}. Status code: 503. "
                    "The server is temporarily unavailable.",
                )
                return default_return_value
            except MastodonAPIError:
                logging.exception(
                    f"Error with Mastodon API on server {server}. "
            "Make sure you have the read:statuses scope enabled for your access token.",
                )
                return default_return_value
            except MastodonError:
                logging.exception(f"Error with Mastodon API on server {server}.")
                return default_return_value
            except KeyError:
                logging.exception(
                    f"Error with Mastodon API on server {server}. "
                    "The response from the server was unexpected.",
                )
                return default_return_value
            except Exception:
                logging.exception("Unhandled error.")
                raise

        return wrapper

    return decorator

def mastodon(server: str, token: str | None = None) -> Mastodon:
    """Get a Mastodon instance."""
    if not hasattr(mastodon, "sessions"):
        mastodon.sessions = {}

    if server not in mastodon.sessions or (
        token is not None and mastodon.sessions[server].access_token is None):
        logging.warning(f"Creating Mastodon session for {server}")
        session = requests.Session()
        session.headers.update({
            "User-Agent": "FediFetcher (https://go.thms.uk/mgr)",
        })
        mastodon.sessions[server] = Mastodon(
            access_token=token if token else None,
            api_base_url=server if server else helpers.arguments.server,
            session=session,
            debug_requests=False,
            ratelimit_method="wait",
            ratelimit_pacefactor=1.1,
            request_timeout=300,
        )
    return mastodon.sessions[server]

@handle_mastodon_errors(None)
def get_user_id(
        user : str,
        server: str,
        token : str | None = None,
        ) -> str | None:
    """Get the user id from the server using a username.

    This function retrieves the user id from the server by \
        performing a search based on the provided username.

    Args:
    ----
    server (str): The server to get the user id from.
    token (str): The access token to use for the request.
    user (str): The username for which to retrieve the user id.

    Returns:
    -------
    str | None: The user id if found, or None if the user is not found.
    """
    if server == helpers.arguments.server or not server:
        return mastodon(server, token).account_lookup(
            acct = f"{user}@{server}",
        )[id]
    account_search = mastodon(server, token).account_lookup(
        acct = f"{user}@{server}",
    )
    if account_search["username"] == user:
        return account_search["id"]
    return None

@handle_mastodon_errors([])
def get_timeline(
    server: str,
    token: str | None = None,
    timeline: str = "local",
    limit: int = 40,
) -> Iterator[dict]:
    """Get all posts in the user's home timeline.

    Args:
    ----
    timeline (str): The timeline to get.
    token (str): The access token to use for the request.
    server (str): The server to get the timeline from.
    limit (int): The maximum number of posts to get.

    Yields:
    ------
    dict: A post from the timeline.

    Raises:
    ------
    Exception: If the access token is invalid.
    Exception: If the access token does not have the correct scope.
    Exception: If the server returns an unexpected status code.
    """
    toots: list[dict] = mastodon(server, token).timeline(
        timeline=timeline, limit=limit)
    number_of_toots_received = len(toots)
    yield from toots
    while toots and number_of_toots_received < limit \
            and toots[-1].get("_pagination_next"):
        more_toots = mastodon(server, token).fetch_next(toots)
        if not more_toots:
            break
        number_of_toots_received += len(more_toots)
        yield from more_toots
    logging.info(f"Found {number_of_toots_received} toots in timeline")

@handle_mastodon_errors(None)
def get_active_user_ids(
        server : str,
        access_token : str,
        reply_interval_hours : int,
        ) -> Generator[str, None, None]:
    """Get all user IDs on the server that have posted in the given time interval.

    Args:
    ----
    server (str): The server to get the user IDs from.
    access_token (str): The access token to use for authentication.
    reply_interval_hours (int): The number of hours to look back for activity.


    Returns:
    -------
    Generator[str, None, None]: A generator of user IDs.


    Raises:
    ------
    Exception: If the access token is invalid.
    Exception: If the access token does not have the correct scope.
    Exception: If the server returns an unexpected status code.
    """
    logging.debug(f"Getting active user IDs for {server}")
    logging.debug(f"Reply interval: {reply_interval_hours} hours")
    since = datetime.now(UTC) - timedelta(days=reply_interval_hours / 24 + 1)
    logging.debug(f"Since: {since}")
    local_accounts = mastodon(server, access_token).admin_accounts_v2(
        origin="local",
        status="active",
        )
    logging.debug(f"Found {len(local_accounts)} accounts")
    if local_accounts:
        logging.debug(
f"Getting user IDs for {len(local_accounts)} local accounts")
        for user in local_accounts:
            logging.debug(f"User: {user.username}")
            last_status_at = user["account"]["last_status_at"]
            logging.debug(f"Last status at: {last_status_at}")
            if last_status_at:
                last_active = last_status_at.astimezone(UTC)
                logging.debug(f"Last active: {last_active}")
                if last_active > since:
                    logging.info(f"Found active user: {user['username']}")
                    yield user["id"]

@handle_mastodon_errors(None)
def get_me(server : str, token : str) -> str | None:
    """Get the user ID of the authenticated user.

    Args:
    ----
    token (str): The access token to use for authentication.
    server (str): The server to get the user ID from. Defaults to the server \
        specified in the arguments.

    Returns:
    -------
    str: The user ID of the authenticated user.

    Raises:
    ------
    Exception: If the access token is invalid.
    Exception: If the access token does not have the correct scope.
    Exception: If the server returns an unexpected status code.
    """
    return mastodon(server, token).account_verify_credentials()["id"]

@handle_mastodon_errors(None)
def get_user_posts_from_id(
        user_id : str,
        server : str,
        token : str | None = None,
        ) -> list[dict[str, str]] | None:
    """Get a list of posts from a user.

    Args:
    ----
    user_id (str): The user id of the user to get the posts from.
    server (str): The server to get the posts from.
    token (str): The access token to use for the request.

    Returns:
    -------
    list[dict[str, str]] | None: A list of posts from the user, or None if \
        the user is not found.

    Raises:
    ------
    Exception: If the access token is invalid.
    Exception: If the access token does not have the correct scope.
    Exception: If the server returns an unexpected status code.
    """
    return mastodon(server, token).account_statuses(
        id = user_id,
        limit = 40,
        )

def get_reply_posts_from_id(
        user_id : str,
        server : str,
        token : str,
        seen_urls : OrderedSet,
        reply_since : datetime,
        ) -> Iterable[dict[str, str]] | None:
    """Get a list of posts from a user.

    Args:
    ----
    user_id (str): The user id of the user to get the posts from.
    server (str): The server to get the posts from.
    token (str): The access token to use for the request.
    seen_urls (OrderedSet[str]): The URLs that have already been seen.
    reply_since (datetime): The datetime to get replies since.

    Returns:
    -------
    list[dict[str, str]] | None: A list of posts from the user, or None if \
        the user is not found.
    """
    try:
        all_statuses = get_user_posts_from_id(user_id, server, token)
        if all_statuses:
            [
                toot
                for toot in all_statuses
                if toot["in_reply_to_id"]
                and datetime.strptime(
                    toot["created_at"],
                        "%Y-%m-%dT%H:%M:%S.%fZ").astimezone(UTC) > reply_since
                and toot["url"] not in seen_urls
                ]
    except Exception:
        logging.exception(
f"Error getting user posts for user {user_id}")
        raise

@handle_mastodon_errors([])
def get_toot_context(
        server : str,
        toot_id : str,
        token : str | None = None,
        ) -> list[str]:
    """Get the context of a toot.

    Args:
    ----
    server (str): The server to get the context from.
    toot_id (str): The ID of the toot to get the context of.
    token (str): The access token to use for the request.

    Returns:
    -------
    list[str] | None: A list of toot URLs in the context of the toot, or [] \
        if the toot is not found.
    """
    context = mastodon(server, token).status_context(
        id = toot_id,
        )
    context_urls: list[str] = [toot["url"] for toot in context["ancestors"]] + \
        [toot["url"] for toot in context["descendants"]]
    return context_urls

@handle_mastodon_errors([])
def get_notifications(
        server : str,
        token : str,
        limit : int = 40,
        ) -> Iterator[dict[str, str]]:
    """Get a list of notifications.

    Args:
    ----
    server (str): The server to get the notifications from.
    token (str): The access token to use for the request.
    limit (int): The maximum number of notifications to get.

    Returns:
    -------
    list[dict[str, str]]: A list of notifications, or [] if the \
        request fails.
    """
    notifications = mastodon(server, token).notifications(limit=limit)
    number_of_notifications_received = len(notifications)
    yield from notifications
    while notifications and number_of_notifications_received < limit \
            and notifications[-1].get("_pagination_next"):
        more_notifications = mastodon(server, token).fetch_next(notifications)
        if not more_notifications:
            break
        number_of_notifications_received += len(more_notifications)
        yield from more_notifications

@handle_mastodon_errors([])
def get_bookmarks(
        server : str,
        token : str,
        limit : int = 40,
        ) -> Iterator[dict[str, str]]:
    """Get a list of bookmarks.

    Args:
    ----
    server (str): The server to get the bookmarks from.
    token (str): The access token to use for the request.
    limit (int): The maximum number of bookmarks to get.

    Returns:
    -------
    list[dict[str, str]]: A list of bookmarks, or [] if the \
        request fails.
    """
    bookmarks = mastodon(server, token).bookmarks(limit=limit)
    number_of_bookmarks_received = len(bookmarks)
    yield from bookmarks
    while bookmarks and number_of_bookmarks_received < limit \
            and bookmarks[-1].get("_pagination_next"):
        more_bookmarks = mastodon(server, token).fetch_next(bookmarks)
        if not more_bookmarks:
            break
        number_of_bookmarks_received += len(more_bookmarks)
        yield from more_bookmarks

@handle_mastodon_errors([])
def get_favourites(
        server : str,
        token : str,
        limit : int = 40,
        ) -> Iterator[dict[str, str]]:
    """Get a list of favourites.

    Args:
    ----
    server (str): The server to get the favourites from.
    token (str): The access token to use for the request.
    limit (int): The maximum number of favourites to get.

    Returns:
    -------
    list[dict[str, str]]: A list of favourites, or [] if the \
        request fails.
    """
    favourites = mastodon(server, token).favourites(limit=limit)
    number_of_favourites_received = len(favourites)
    yield from favourites
    while number_of_favourites_received < limit \
            and favourites[-1].get("_pagination_next"):
        more_favourites = mastodon(server, token).fetch_next(favourites)
        if not more_favourites:
            break
        number_of_favourites_received += len(more_favourites)
        yield from more_favourites

@handle_mastodon_errors([])
def get_follow_requests(
        server : str,
        token : str,
        limit : int = 40,
        ) -> Iterator[dict[str, str]]:
    """Get a list of follow requests.

    Args:
    ----
    server (str): The server to get the follow requests from.
    token (str): The access token to use for the request.
    limit (int): The maximum number of follow requests to get.

    Returns:
    -------
    list[dict[str, str]]: A list of follow requests, or [] if the \
        request fails.
    """
    follow_requests = mastodon(server, token).follow_requests(limit=limit)
    number_of_follow_requests_received = len(follow_requests)
    yield from follow_requests
    while follow_requests and number_of_follow_requests_received < limit \
            and follow_requests[-1].get("_pagination_next"):
        more_follow_requests = mastodon(server, token).fetch_next(follow_requests)
        if not more_follow_requests:
            break
        number_of_follow_requests_received += len(more_follow_requests)
        yield from more_follow_requests

@handle_mastodon_errors([])
def get_followers(
        server : str,
        token : str | None,
        user_id : str,
        limit : int = 40,
        ) -> Iterator[dict[str, str]]:
    """Get a list of followers.

    Args:
    ----
    server (str): The server to get the followers from.
    token (str): The access token to use for the request.
    user_id (str): The user ID of the user to get the followers of.
    limit (int): The maximum number of followers to get.

    Returns:
    -------
    list[dict[str, str]]: A list of followers, or [] if the \
        request fails.
    """
    followers = mastodon(server, token).account_followers(id=user_id,limit=limit)
    number_of_followers_received = len(followers)
    yield from followers
    while followers and number_of_followers_received < limit \
            and followers[-1].get("_pagination_next"):
        more_followers = mastodon(server, token).fetch_next(followers)
        if not more_followers:
            break
        number_of_followers_received += len(more_followers)
        yield from more_followers

@handle_mastodon_errors([])
def get_following(
        server : str,
        token : str | None,
        user_id : str,
        limit : int = 40,
        ) -> Iterator[dict[str, str]]:
    """Get a list of following.

    Args:
    ----
    server (str): The server to get the following from.
    token (str): The access token to use for the request.
    user_id (str): The user ID of the user to get the following of.
    limit (int): The maximum number of following to get.

    Returns:
    -------
    list[dict[str, str]]: A list of following, or [] if the \
        request fails.
    """
    following = mastodon(server, token).account_following(id=user_id,limit=limit)
    number_of_following_received = len(following)
    yield from following
    while following and number_of_following_received < limit \
            and following[-1].get("_pagination_next"):
        more_following = mastodon(server, token).fetch_next(following)
        if not more_following:
            break
        number_of_following_received += len(more_following)
        yield from more_following

@handle_mastodon_errors(default_return_value=False)
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
    # Use mastodon.py add the toot to the server.
    mastodon(server, access_token).search_v2(
        q = url,
    )
    return True
