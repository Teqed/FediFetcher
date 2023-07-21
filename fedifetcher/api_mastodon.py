"""Mastodon API functions."""
import asyncio
import functools
import inspect
import logging
from collections.abc import Awaitable, Callable, Iterable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar, cast
import concurrent.futures
import requests
from mastodon import (
    Mastodon,
    MastodonAPIError,
    MastodonError,
    MastodonNetworkError,
    MastodonNotFoundError,
    MastodonRatelimitError,
    MastodonServiceUnavailableError,
    MastodonUnauthorizedError,
)
from mastodon.types import Context, Status

from fedifetcher.postgresql import PostgreSQLUpdater

from . import helpers

T = TypeVar("T")
def handle_mastodon_errors(  # noqa: C901
        default_return_value: T, # type: ignore  # noqa: PGH003
        ) -> Callable:
    """Handle Mastodon errors."""
    def decorator(  # noqa: C901
            func: Callable[..., T | None]) -> Callable[..., T | None]:
        sig = inspect.signature(func)

        @functools.wraps(func)
        def wrapper(  # noqa: PLR0911
            *args: Any, **kwargs: Any) -> T | None:  # noqa: ANN401
            bound = sig.bind(*args, **kwargs)

            server = bound.arguments.get("server", "Unknown")

            try:
                return func(*args, **kwargs)
            except MastodonNotFoundError:
                logging.error(
                    f"Error with Mastodon API on server {server}. Status code: 404. "
                    "Ensure the server endpoint is reachable.",
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
            except MastodonNetworkError as ex:
                logging.error(
                    f"Error with Mastodon API on server {server}. "
                    f"The server encountered an error: {ex} ",
                )
            except MastodonAPIError as ex:
                logging.error(
                    f"Error with Mastodon API on server {server} : {ex}",
            # Make sure you have the read:statuses scope enabled for your access token.
                )
                return default_return_value
            except MastodonError as ex:
                logging.error(f"Error with Mastodon API on server {server}: {ex}")
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
        msg = f"Creating Mastodon session for {server}"
        logging.info(f"\033[1;33m{msg}\033[0m")
        if token:
            msg = "Using provided token"
            logging.info(f"\033[1;33m{msg}\033[0m")
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 +https://github.com/Teqed Meowstodon/1.0.0",  # noqa: E501
        })
        rate_limit_method = "wait" if not mastodon.sessions else "throw"
        mastodon.sessions[server] = Mastodon(
            access_token=token if token else None,
            api_base_url=server if server else helpers.arguments.server,
            session=session,
            debug_requests=False,
            ratelimit_method=rate_limit_method,
            ratelimit_pacefactor=1.1,
            request_timeout=7,
            version_check_mode="none",
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
        return (mastodon(server, token)).account_lookup(
            acct = f"{user}",
        )[id]
    account_search = (mastodon(server, token)).account_lookup(
        acct = f"{user}",
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
) -> list[dict[str, str]]:
    """Get all posts in the user's home timeline.

    Args:
    ----
    timeline (str): The timeline to get.
    token (str): The access token to use for the request.
    server (str): The server to get the timeline from.
    limit (int): The maximum number of posts to get.

    Returns:
    -------
    list[dict]: A list of posts from the timeline.

    Raises:
    ------
    Exception: If the access token is invalid.
    Exception: If the access token does not have the correct scope.
    Exception: If the server returns an unexpected status code.
    """
    toots = cast(list[dict[str, str]], (
        mastodon(server, token)).timeline(timeline=timeline, limit=limit))
    toots_result = toots.copy()
    number_of_toots_received = len(toots)
    while toots and number_of_toots_received < limit and \
            toots[-1].get("_pagination_next"):
        toots = (mastodon(server, token)).fetch_next(toots)
        if not toots:
            break
        number_of_toots_received += len(toots)
        toots_result.extend(toots)
    logging.info(f"Found {number_of_toots_received} posts in timeline")
    return toots_result

@handle_mastodon_errors(None)
def get_active_user_ids(
    server: str,
    access_token: str,
    reply_interval_hours: int,
) -> list[str]:
    """Get all user IDs on the server that have posted in the given time interval.

    Args:
    ----
    server (str): The server to get the user IDs from.
    access_token (str): The access token to use for authentication.
    reply_interval_hours (int): The number of hours to look back for activity.

    Returns:
    -------
    list[str]: A list of user IDs.

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
    local_accounts = (mastodon(server, access_token)).admin_accounts_v2(
        origin="local",
        status="active",
    )
    logging.debug(f"Found {len(local_accounts)} accounts")
    active_user_ids = []
    if local_accounts:
        logging.debug(f"Getting user IDs for {len(local_accounts)} local accounts")
        for user in local_accounts:
            logging.debug(f"User: {user.username}")
            last_status_at = user.account.last_status_at
            logging.debug(f"Last status at: {last_status_at}")
            if last_status_at:
                last_active = last_status_at.astimezone(UTC)
                logging.debug(f"Last active: {last_active}")
                if last_active > since:
                    logging.info(f"Found active user: {user.username}")
                    active_user_ids.append(str(user.id))
    return active_user_ids

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
    return (mastodon(server, token)).account_verify_credentials()["id"]

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
    logging.info(f"Getting posts for user {user_id} on {server}")
    return cast(list[dict[str, str]],
                (mastodon(server, token)).account_statuses(
                    id = user_id,
                    limit = 40,
                    ))

def get_reply_posts_from_id(
    user_id: str,
    server: str,
    token: str,
    pgupdater: PostgreSQLUpdater,
    reply_since: datetime,
) -> list[dict[str, str]] | None:
    """Get a list of posts from a user.

    Args:
    ----
    user_id (str): The user id of the user to get the posts from.
    server (str): The server to get the posts from.
    token (str): The access token to use for the request.
    pgupdater (PostgreSQLUpdater): The PostgreSQL updater.
    reply_since (datetime): The datetime to get replies since.

    Returns:
    -------
    list[dict[str, str]] | None: A list of posts from the user, or None if \
        the user is not found.
    """
    try:
        all_statuses = get_user_posts_from_id(user_id, server, token)
        if all_statuses:
            return [
                toot
                for toot in all_statuses
                if toot["in_reply_to_id"]
                and cast(datetime, toot["created_at"]).astimezone(UTC) > reply_since
                and pgupdater.get_from_cache(toot["url"]) is None
            ]
    except Exception:
        logging.exception(f"Error getting user posts for user {user_id}")
        raise
    return None

@handle_mastodon_errors([])
def get_toot_context(  # noqa: PLR0913
        server: str, toot_id: str, token: str | None,
        pgupdater: PostgreSQLUpdater, home_server: str,
        home_server_token: str) -> list[str]:
    """Get the URLs of the context toots of the given toot asynchronously."""
    # Get the context of a toot
    context: Context = (mastodon(server, token)).status_context(id=toot_id)
    # List of status URLs
    context_statuses = list(context["ancestors"] + context["descendants"])
    # Sort by server
    context_statuses.sort(key=lambda status: status["url"].split("/")[2])
    context_statuses_url_list = [status["url"] for status in context_statuses]
    home_status_list: dict[str, str] = get_home_status_id_from_url_list(
        home_server, home_server_token, context_statuses_url_list, pgupdater)
    for status in context_statuses:
        home_status_id = home_status_list.get(status["url"])
        if home_status_id:
            pgupdater.queue_status_update(
                int(home_status_id),
                status.get("reblogs_count"), status.get("favourites_count"))
    # Commit status updates
    pgupdater.commit_status_updates()
    return [status["url"] for status in context_statuses]

@handle_mastodon_errors([])
def get_notifications(
    server: str,
    token: str,
    limit: int = 40,
) -> list[dict[str, str]]:
    """Get a list of notifications.

    Args:
    ----
    server (str): The server to get the notifications from.
    token (str): The access token to use for the request.
    limit (int): The maximum number of notifications to get.

    Returns:
    -------
    list[dict[str, str]]: A list of notifications, or [] if the request fails.
    """
    notifications = (mastodon(server, token)).notifications(limit=limit)
    number_of_notifications_received = len(notifications)
    notifications_result = notifications.copy()
    while notifications \
            and number_of_notifications_received < limit \
                and notifications[-1].get("_pagination_next"):
        more_notifications = (mastodon(server, token)).fetch_next(notifications)
        if not more_notifications:
            break
        number_of_notifications_received += len(more_notifications)
        notifications_result.extend(more_notifications)
    return cast(list[dict[str, str]], notifications_result)

@handle_mastodon_errors([])
def get_bookmarks(
    server: str,
    token: str,
    limit: int = 40,
) -> list[dict[str, str]]:
    """Get a list of bookmarks.

    Args:
    ----
    server (str): The server to get the bookmarks from.
    token (str): The access token to use for the request.
    limit (int): The maximum number of bookmarks to get.

    Returns:
    -------
    list[dict[str, str]]: A list of bookmarks, or [] if the request fails.
    """
    bookmarks = (mastodon(server, token)).bookmarks(limit=limit)
    number_of_bookmarks_received = len(bookmarks)
    bookmarks_result = bookmarks.copy()
    while bookmarks \
            and number_of_bookmarks_received < limit \
                and bookmarks[-1].get("_pagination_next"):
        more_bookmarks = (mastodon(server, token)).fetch_next(bookmarks)
        if not more_bookmarks:
            break
        number_of_bookmarks_received += len(more_bookmarks)
        bookmarks_result.extend(more_bookmarks)
    return cast(list[dict[str, str]], bookmarks_result)

@handle_mastodon_errors([])
def get_favourites(
    server: str,
    token: str,
    limit: int = 40,
) -> list[dict[str, str]]:
    """Get a list of favourites.

    Args:
    ----
    server (str): The server to get the favourites from.
    token (str): The access token to use for the request.
    limit (int): The maximum number of favourites to get.

    Returns:
    -------
    list[dict[str, str]]: A list of favourites, or [] if the request fails.
    """
    favourites = (mastodon(server, token)).favourites(limit=limit)
    number_of_favourites_received = len(favourites)
    favourites_result = favourites.copy()
    while number_of_favourites_received < limit \
            and favourites[-1].get("_pagination_next"):
        more_favourites = (mastodon(server, token)).fetch_next(favourites)
        if not more_favourites:
            break
        number_of_favourites_received += len(more_favourites)
        favourites_result.extend(more_favourites)
    return cast(list[dict[str, str]], favourites_result)

@handle_mastodon_errors([])
def get_follow_requests(
    server: str,
    token: str,
    limit: int = 40,
) -> list[dict[str, str]]:
    """Get a list of follow requests.

    Args:
    ----
    server (str): The server to get the follow requests from.
    token (str): The access token to use for the request.
    limit (int): The maximum number of follow requests to get.

    Returns:
    -------
    list[dict[str, str]]: A list of follow requests, or [] if the request fails.
    """
    follow_requests = (mastodon(server, token)).follow_requests(limit=limit)
    number_of_follow_requests_received = len(follow_requests)
    follow_requests_result = follow_requests.copy()
    while follow_requests \
            and number_of_follow_requests_received < limit \
                and follow_requests[-1].get("_pagination_next"):
        more_follow_requests = (
            mastodon(server, token)).fetch_next(follow_requests)
        if not more_follow_requests:
            break
        number_of_follow_requests_received += len(more_follow_requests)
        follow_requests_result.extend(more_follow_requests)
    return cast(list[dict[str, str]], follow_requests_result)

@handle_mastodon_errors([])
def get_followers(
    server: str,
    token: str | None,
    user_id: str,
    limit: int = 40,
) -> list[dict[str, str]]:
    """Get a list of followers.

    Args:
    ----
    server (str): The server to get the followers from.
    token (str): The access token to use for the request.
    user_id (str): The user ID of the user to get the followers of.
    limit (int): The maximum number of followers to get.

    Returns:
    -------
    list[dict[str, str]]: A list of followers, or [] if the request fails.
    """
    followers = (
        mastodon(server, token)).account_followers(id=user_id, limit=limit)
    number_of_followers_received = len(followers)
    followers_result = followers.copy()
    while followers \
            and number_of_followers_received < limit \
                and followers[-1].get("_pagination_next"):
        more_followers = (mastodon(server, token)).fetch_next(followers)
        if not more_followers:
            break
        number_of_followers_received += len(more_followers)
        followers_result.extend(more_followers)
    return cast(list[dict[str, str]], followers_result)

@handle_mastodon_errors([])
def get_following(
    server: str,
    token: str | None,
    user_id: str,
    limit: int = 40,
) -> list[dict[str, str]]:
    """Get a list of following.

    Args:
    ----
    server (str): The server to get the following from.
    token (str): The access token to use for the request.
    user_id (str): The user ID of the user to get the following of.
    limit (int): The maximum number of following to get.

    Returns:
    -------
    list[dict[str, str]]: A list of following, or [] if the request fails.
    """
    following = (
        mastodon(server, token)).account_following(id=user_id, limit=limit)
    number_of_following_received = len(following)
    following_result = following.copy()
    while following \
            and number_of_following_received < limit \
                and following[-1].get("_pagination_next"):
        more_following = (mastodon(server, token)).fetch_next(following)
        if not more_following:
            break
        number_of_following_received += len(more_following)
        following_result.extend(more_following)
    return cast(list[dict[str, str]], following_result)

@handle_mastodon_errors(default_return_value=False)
def add_context_url(
        url : str,
        server : str,
        access_token : str,
        ) -> Status | bool:
    """Add the given toot URL to the server.

    Args:
    ----
    url: The URL of the toot to add.
    server: The server to add the toot to.
    access_token: The access token to use to add the toot.

    Returns:
    -------
    dict[str, str] | bool: The status of the request, or False if the \
        request fails.
    """
    try:
        result = (mastodon(server, access_token)).search_v2(
            q = url,
        )
    except MastodonAPIError:
        logging.exception(f"Error adding context url {url} to {server}")
        return False
    if result.statuses:
        for _status in result.statuses:
            if _status.url == url:
                return _status
    return False

@handle_mastodon_errors(default_return_value=[])
def get_trending_posts(
        server : str,
        token : str | None = None,
        limit : int = 40,
        ) -> list[dict[str, str]]:
    """Get a list of trending posts.

    Args:
    ----
    server (str): The server to get the trending posts from.
    token (str): The access token to use for the request.
    limit (int): The maximum number of trending posts to get. \
        Defaults to 40. Paginates until the limit is reached.

    Returns:
    -------
    list[dict[str, str]]: A list of trending posts, or [] if the \
        request fails.
    """
    def get_trending_posts(
            server: str,
            token: str | None = None,
            offset: int = 0,
    ) -> list[dict[str, str]]:
        """Get a page of trending posts and return it."""
        getting_trending_posts = mastodon(
            server, token).trending_statuses(limit=40, offset=offset)

        return cast(list[dict[str, str]], getting_trending_posts)

    msg = f"Getting {limit} trending posts for {server}"
    logging.info(f"\033[1m{msg}\033[0m")
    got_trending_posts: list[dict[str, str]] = []
    try:
        got_trending_posts = get_trending_posts(
            server, token, 0)
    except Exception:
        logging.exception(
            f"Error getting trending posts for {server}")
        return []
    logging.info(f"Got {len(got_trending_posts)} trending posts for {server}")
    trending_posts: list[dict[str, str]] = []
    trending_posts.extend(got_trending_posts)
    a_page = 40
    if limit > a_page:
        with concurrent.futures.ThreadPoolExecutor(
            thread_name_prefix="fetcher",
    ) as executor:
            futures = []
            for offset in range(a_page, limit, a_page):
                futures.append(executor.submit(
                    get_trending_posts, server, token, offset))
            for future in concurrent.futures.as_completed(futures):
                try:
                    got_trending_posts = future.result()
                except Exception:
                    logging.exception(
                        f"Error getting trending posts for {server}")
                    break
                trending_posts.extend(got_trending_posts)
                logging.info(
                    f"Got {len(trending_posts)} trending posts for {server} ...")

        # offset = a_page
        # while len(trending_posts) < limit:
        #     try:
        #         got_trending_posts = get_trending_posts(
        #             server, token, offset)
        #     except Exception:
        #         logging.exception(
        #             f"Error getting trending posts for {server}")
        #         break
        #     trending_posts.extend(got_trending_posts)
        #     if len(got_trending_posts) < a_page:
        #         logging.info(
        #         f"Got {len(got_trending_posts)} trending posts total for {server} .")
        #         break
        #     logging.info(
        #         f"Got {len(trending_posts)} trending posts for {server} ...")
        #     offset += a_page
        # ###################
        # offset_list = [40+i*40 for i in range(3)]
        # tasks = [asyncio.create_task(
        #     get_trending_posts_async(
        #         server, token, off)) for off in offset_list]
        # highest_offset = max(offset_list)
        # while tasks:
        #     done, pending = asyncio.wait(
        #         tasks, return_when=asyncio.FIRST_COMPLETED)
        #     for task in done:
        #         try:
        #             result = task.result()
        #             if len(result) == 0:
        #                 break  # stop processing results
        #             trending_posts.extend(result)
        #             logging.info(
        #                 f"Got {len(trending_posts)} trending posts for {server} ...")
        #             if len(trending_posts) >= limit:
        #                 break
        #             highest_offset += 40
        #             new_task = asyncio.create_task(
        #                 get_trending_posts_async(
        #                     server, token, highest_offset)) # create a task
        #             tasks.append(new_task)  # add it to the set
        #         except MastodonError:
        #             logging.exception(
        #                 f"Error getting trending posts for {server}")
        #             break
        #     tasks = [t for t in tasks if not t.done()]  # remove

    logging.info(f"Found {len(trending_posts)} trending posts for {server}")
    return trending_posts

def filter_language(
        toots : Iterable[dict[str, str]],
        language : str,
        ) -> Iterator[dict[str, str]]:
    """Filter out toots that are not in the given language.

    Args:
    ----
    toots (Iterable[dict[str, str]]): The toots to filter.
    language (str): The language to filter by.

    Returns:
    -------
    Iterator[dict[str, str]]: The filtered toots.
    """
    return filter(
        lambda toot: toot.get("language") == language, toots)

@handle_mastodon_errors(None)
def get_home_status_id_from_url(
        server: str,
        token: str,
        url: str,
        pgupdater: PostgreSQLUpdater,
) -> str | None:
    """Get the status id from a toot URL asynchronously.

    Args:
    ----
    server (str): The server to get the status id from.
    token (str): The access token to use for the request.
    url (str): The URL of the toot to get the status id of.
    pgupdater (PostgreSQLUpdater): The PostgreSQLUpdater instance to use for \
        caching the status.

    Returns:
    -------
    str | None: The status id of the toot, or None if the toot is not found.
    """
    cached_status = pgupdater.get_from_cache(url)
    if cached_status:
        status_id = cached_status.get("id")
        if status_id is not None:
            return status_id
    msg = f"Fetching status id for {url} from {server}"
    logging.info(f"\033[1;33m{msg}\033[0m")
    result = add_context_url(url, server, token)
    if isinstance(result, dict | Status):
        status_id = result.get("id")
        logging.debug(f"Got status id {status_id} for {url} from {server}")
        if result.get("url") == url:
            pgupdater.cache_status(result)
            return str(status_id)
        logging.error(
            f"Something went wrong fetching: {url} from {server} , \
did not match {result.get('url')}")
        logging.debug(result)
    elif result is False:
        logging.warning(f"Failed to get status id for {url} on {server}")
    logging.error(f"Status id for {url} not found")
    return None

@handle_mastodon_errors(None)
def get_home_status_id_from_url_list(
        server: str,
        token: str,
        urls: list[str],
        pgupdater: PostgreSQLUpdater,
) -> dict[str, str]:
    """Get the status ids from a list of toot URLs asynchronously.

    Args:
    ----
    server (str): The server to get the status id from.
    token (str): The access token to use for the request.
    urls (list[str]): The URLs of the toots to get the status ids of.
    pgupdater (PostgreSQLUpdater): The PostgreSQLUpdater instance to use for \
        caching the status.

    Returns:
    -------
    dict[str, str]: A dict of status ids, keyed by toot URL.
    """
    status_ids = {}
    cached_statuses: dict[str, Status | None] = \
        pgupdater.get_dict_from_cache(urls)
    for url in urls:
        if cached_statuses:
            cached_status = cached_statuses.get(url)
            if cached_status:
                status_id = cached_status.get("id")
                if status_id:
                    status_ids.update({url: status_id})
                    continue
        status_id = get_home_status_id_from_url(
            server, token, url, pgupdater)
        if status_id:
            status_ids.update({url: status_id})
    return status_ids

@handle_mastodon_errors(None)
def get_status_by_id(
        server: str,
        status_id : str,
        external_tokens : dict[str, str] | None,
        ) -> dict[str, str] | None:
    """Get the status from a toot URL.

    Args:
    ----
    server (str): The server to get the status from.
    status_id (str): The ID of the toot to get the status of.
    external_tokens (dict[str, str] | None): A dict of external tokens, keyed \
        by server. If None, no external tokens will be used.

    Returns:
    -------
    dict[str, str] | None: The status of the toot, or None if the toot is not found.
    """
    token = None
    if external_tokens and server in external_tokens:
        token = external_tokens[server]
    return (mastodon(server, token)).status(status_id)
