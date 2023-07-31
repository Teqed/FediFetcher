"""Mastodon API functions."""
import ast
import concurrent.futures
import functools
import inspect
import logging
from collections.abc import Callable, Coroutine, Iterable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar, TypeVar, cast

import aiohttp
from helpers import Response
from mastodon import (
    MastodonAPIError,
    MastodonError,
    MastodonNetworkError,
    MastodonNotFoundError,
    MastodonRatelimitError,
    MastodonServiceUnavailableError,
    MastodonUnauthorizedError,
)
from mastodon.types import Context, Status

from fedifetcher import api_firefish
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

class MastodonClient:
    """A class representing a Mastodon client."""

    def __init__(self,
                    api_base_url: str,
                    client: aiohttp.ClientSession,
                    token: str | None = None,
                    ) -> None:
            """Initialize the Mastodon client."""
            self.api_base_url = api_base_url
            self.token = token
            self.client = client

    async def get(self,
        endpoint: str, params: dict | None = None) -> dict[str, Any]:
        """Perform a GET request to the Mastodon server."""
        async with self.client.get(
            f"{self.api_base_url}{endpoint}",
            headers={
                "Authorization": f"Bearer {self.token}",
            },
            params=params,
        ) as response:
            return await self.handle_response_errors(response)

    async def handle_response_errors(self, response: aiohttp.ClientResponse,
        ) -> dict:
        """Handle errors in the response."""
        if response.status == Response.OK:
            body = await response.json()
            if body:
                if isinstance(body, list):
                    body = {"list": body}
                if not isinstance(body, dict):
                    logging.error(
                        f"Error with Mastodon API on server {self.api_base_url}. "
                        f"The server returned an unexpected response: {body}",
                    )
                    return {}
                link_header = response.headers.get("Link")
                if link_header:
                    links = {}
                    link_parts = link_header.split(", ")
                    for link_part in link_parts:
                        url, rel = link_part.split("; ")
                        url = url.strip("<>")
                        rel = rel.strip('rel="')
                        links[rel] = url
                    if links.get("next"):
                        body["_pagination_next"] = links["next"]
                    if links.get("prev"):
                        body["_pagination_prev"] = links["prev"]
                return body
            return {"Status": "OK"}
        if response.status == Response.BAD_REQUEST:
            logging.error(
                f"Error with Mastodon API on server {self.api_base_url}. "
                f"400 Client error: {response}",
            )
        elif response.status == Response.UNAUTHORIZED:
            logging.error(
                f"Error with Mastodon API on server {self.api_base_url}. "
                f"401 Authentication error: {response}",
            )
        elif response.status == Response.FORBIDDEN:
            logging.error(
                f"Error with Mastodon API on server {self.api_base_url}. "
                f"403 Forbidden error: {response}",
            )
        elif response.status == Response.TOO_MANY_REQUESTS:
            logging.error(
                f"Error with Mastodon API on server {self.api_base_url}. "
                f"429 Too many requests: {response}",
            )
        elif response.status == Response.INTERNAL_SERVER_ERROR:
            logging.warning(
                f"Error with Mastodon API on server {self.api_base_url}. "
                f"500 Internal server error: {response}",
            )
        else:
            logging.error(
                f"Error with Mastodon API on server {self.api_base_url}. "
                f"The server encountered an error: {response}",
            )
        return {}

class Mastodon:
    """A class representing a Mastodon instance."""

    clients : ClassVar[dict[str, MastodonClient]] = {}
    def __init__(self,
        server: str,
        token: str | None = None,
        pgupdater: PostgreSQLUpdater | None = None,
        ) -> None:
        """Initialize the Mastodon instance."""
        self.server = server
        self.token = token
        self.pgupdater = pgupdater
        if server not in Mastodon.clients or (
            token is not None and Mastodon.clients[server].token is None):
            msg = f"Creating Mastodon client for {server}"
            logging.info(f"\033[1;33m{msg}\033[0m")
            if token:
                msg = "Using provided token"
                logging.info(f"\033[1;33m{msg}\033[0m")
            client = aiohttp.ClientSession(
                headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 +https://github.com/Teqed Meowstodon/1.0.0",  # noqa: E501
            })

            Mastodon.clients[server] = MastodonClient(
                api_base_url=server if server else helpers.arguments.server,
                client=client,
                token=token,
            )
        self.client = Mastodon.clients[server]

    async def get_user_id(
            self,
            user : str,
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
        if self.server == helpers.arguments.server or not self.server:
            account = await self.account_lookup(
                acct = f"{user}",
            )
            if not isinstance(account, bool):
                return account["id"]
        account_search = await self.account_lookup(
            acct = f"{user}",
        )
        if not isinstance(account_search, bool) \
            and account_search["username"] == user:
            return account_search["id"]
        return None

    async def get_timeline(
            self,
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
        timeline_toots = await self.timeline(timeline=timeline, limit=limit)
        if not timeline_toots:
            return []
        toots = cast(list[dict[str, str]], (
            timeline_toots))
        toots_result = toots.copy()
        number_of_toots_received = len(toots)
        while isinstance(toots, dict) and number_of_toots_received < limit and \
                toots.get("_pagination_next"):
            toots = await self.fetch_next(toots)
            if not toots:
                break
            number_of_toots_received += len(toots)
            toots_result.extend(toots)
        logging.info(f"Found {number_of_toots_received} posts in timeline")
        return toots_result

    async def get_active_user_ids(
        self,
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
        logging.debug(f"Getting active user IDs for {self.server}")
        logging.debug(f"Reply interval: {reply_interval_hours} hours")
        since = datetime.now(UTC) - timedelta(days=reply_interval_hours / 24 + 1)
        logging.debug(f"Since: {since}")
        local_accounts = await self.admin_accounts_v2(
            origin="local",
            status="active",
        )
        logging.debug(f"Found {len(local_accounts)} accounts")
        active_user_ids = []
        if local_accounts:
            logging.debug(f"Getting user IDs for {len(local_accounts)} local accounts")
            for user in local_accounts:
                user_dict: dict[str, Any] = ast.literal_eval(user)
                logging.debug(f"User: {user_dict.get('username')}")
                account = user_dict.get("account") or {}
                last_status_at = account.get("last_status_at")
                logging.debug(f"Last status at: {last_status_at}")
                if last_status_at:
                    last_active = last_status_at.astimezone(UTC)
                    logging.debug(f"Last active: {last_active}")
                    if last_active > since:
                        logging.info(f"Found active user: {user_dict.get('username')}")
                        active_user_ids.append(str(user_dict.get("id")))
        return active_user_ids

    async def get_me(self) -> str | None:
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
        return (await self.account_verify_credentials()).get("id")

    async def get_user_posts_from_id(
            self,
            user_id : str,
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
        logging.info(f"Getting posts for user {user_id} on {self.server}")
        return await self.account_statuses(
                        account_id = user_id,
                        limit = 40,
                        )

    async def get_reply_posts_from_id(
        self,
        user_id: str,
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
        if not self.pgupdater:
            return None
        try:
            all_statuses = await self.get_user_posts_from_id(user_id)
            if all_statuses:
                return [
                    toot
                    for toot in all_statuses
                    if toot["in_reply_to_id"]
                    and cast(datetime, toot["created_at"]).astimezone(UTC) > reply_since
                    and self.pgupdater.get_from_cache(toot["url"]) is None
                ]
        except Exception:
            logging.exception(f"Error getting user posts for user {user_id}")
            raise
        return None

    async def get_toot_context(
            self,
            server: str, toot_id: str, token: str | None,
            ) -> list[str]:
        """Get the URLs of the context toots of the given toot asynchronously."""
        # Get the context of a toot
        context: Context = (mastodon(server, token)).status_context(id=toot_id)
        # List of status URLs
        context_statuses = list(context["ancestors"] + context["descendants"])
        # Sort by server
        context_statuses.sort(key=lambda status: status["url"].split("/")[2])
        context_statuses_url_list = [status["url"] for status in context_statuses]
        home_status_list: dict[str, str] = \
            self.get_home_status_id_from_url_list(context_statuses_url_list)
        for status in context_statuses:
            home_status_id = home_status_list.get(status["url"])
            if home_status_id:
                self.pgupdater.queue_status_update(
                    home_status_id,
                    status.get("reblogs_count"), status.get("favourites_count"))
        # Commit status updates
        self.pgupdater.commit_status_updates()
        return [status["url"] for status in context_statuses]

    async def get_notifications(
        self,
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
        notifications_dict = await self.notifications(limit=limit)
        notifications = notifications_dict.get("list")
        if not notifications:
            return []
        number_of_notifications_received = len(notifications)
        notifications_result = notifications.copy()
        while notifications \
                and number_of_notifications_received < limit \
                    and notifications_dict.get("_pagination_next"):
            more_notifications_dict = await self.fetch_next(notifications_dict)
            more_notifications = more_notifications_dict.get("list")
            if not more_notifications:
                break
            number_of_notifications_received += len(more_notifications)
            notifications_result.extend(more_notifications)
        return cast(list[dict[str, str]], notifications_result)

    def get_bookmarks(
        self,
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
        bookmarks = self.bookmarks(limit=limit)
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

    def get_favourites(
        self,
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
        if favourites and favourites[-1]:
            while number_of_favourites_received < limit \
                    and favourites[-1].get("_pagination_next"):
                more_favourites = (mastodon(server, token)).fetch_next(favourites)
                if not more_favourites:
                    break
                number_of_favourites_received += len(more_favourites)
                favourites_result.extend(more_favourites)
        return cast(list[dict[str, str]], favourites_result)

    def get_follow_requests(
        self,
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

    def get_followers(
        self,
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

    def get_following(
        self,
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

    def add_context_url(
            self,
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

    def get_trending_posts(
            self,
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
        def _get_trending_posts(
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
            got_trending_posts = _get_trending_posts(
                server, token, 0)
        except Exception:
            logging.exception(
                f"Error getting trending posts for {server}")
            return []
        logging.info(f"Got {len(got_trending_posts)} trending posts for {server}")
        trending_posts: list[dict[str, str]] = []
        trending_posts.extend(got_trending_posts)
        a_page = 40
        if limit > a_page and len(got_trending_posts) == a_page:
            with concurrent.futures.ThreadPoolExecutor(
                thread_name_prefix="sub_fetcher",
        ) as executor:
                futures = []
                for offset in range(a_page, limit, a_page):
                    futures.append(executor.submit(
                        _get_trending_posts, server, token, offset))
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

            # while len(trending_posts) < limit:
            #             server, token, offset)
            #         logging.exception(
            #             f"Error getting trending posts for {server}")
            #     if len(got_trending_posts) < a_page:
            #         logging.info(
            #         f"Got {len(got_trending_posts)} trending posts total for {server} .")
            #     logging.info(
            #         f"Got {len(trending_posts)} trending posts for {server} ...")
            # ###################
            #     get_trending_posts_async(
            #         server, token, off)) for off in offset_list]
            # while tasks:
            #         tasks, return_when=asyncio.FIRST_COMPLETED)
            #     for task in done:
            #             if len(result) == 0:
            #             logging.info(
            #                 f"Got {len(trending_posts)} trending posts for {server} ...")
            #             if len(trending_posts) >= limit:
            #                 get_trending_posts_async(
            #                     server, token, highest_offset)) # create a task
            #             logging.exception(
            #                 f"Error getting trending posts for {server}")

        logging.info(f"Found {len(trending_posts)} trending posts for {server}")
        return trending_posts

    def filter_language(
            self,
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

    def get_home_status_id_from_url(
            self,
            home_server: str,
            token: str,
            url: str,
            pgupdater: PostgreSQLUpdater,
    ) -> str | None:
        """Get the status id from a toot URL asynchronously.

        Args:
        ----
        home_server (str): The server to get the status id from.
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
        msg = f"Fetching status id for {url} from {home_server}"
        logging.info(f"\033[1;33m{msg}\033[0m")
        result = self.add_context_url(url, home_server, token)
        if isinstance(result, dict | Status):
            if result.get("url") == url:
                status = pgupdater.get_from_cache(url)
                status_id = status.get("id") if status else None
                logging.info(f"Got status id {status_id} for {url} from {home_server}")
                return str(status_id)
            logging.error(
                f"Something went wrong fetching: {url} from {home_server} , \
    did not match {result.get('url')}")
            logging.debug(result)
        elif result is False:
            logging.warning(f"Failed to get status id for {url} on {home_server}")
        logging.error(f"Status id for {url} not found")
        return None

    async def get_home_status_id_from_url_list(
            self,
            urls: list[str],
    ) -> dict[str, str]:
        """Get the status ids from a list of toot URLs asynchronously.

        Args:
        ----
        home_server (str): The server to get the status id from.
        token (str): The access token to use for the request.
        urls (list[str]): The URLs of the toots to get the status ids of.
        pgupdater (PostgreSQLUpdater): The PostgreSQLUpdater instance to use for \
            caching the status.

        Returns:
        -------
        dict[str, str]: A dict of status ids, keyed by toot URL.
        """
        if not self.pgupdater:
            return {}
        status_ids = {}
        cached_statuses: dict[str, Status | None] = \
            self.pgupdater.get_dict_from_cache(urls)
        with concurrent.futures.ThreadPoolExecutor(
            thread_name_prefix="id_getter",
            max_workers=9,
        ) as executor:
            futures = {}
            for url in urls:
                cached_status = cached_statuses.get(url)
                if cached_status:
                    status_id = cached_status.get("id")
                    if status_id is not None:
                        status_ids[url] = str(status_id)
                        continue
                futures[url] = executor.submit(
                    api_firefish.Firefish(
                        home_server, token, pgupdater).get_home_status_id_from_url, url)
            for url, future in futures.items():
                try:
                    status_id = future.result()
                except Exception:
                    logging.exception(
                        f"Error getting status id for {url} from {home_server}")
                    continue
                if status_id is not None:
                    status_ids[url] = status_id
        return status_ids

    async def get_status_by_id(
            self,
            status_id : str,
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
        return await self.status(status_id)

    def status(
            self,
            status_id: str,
        ) -> Coroutine[Any, Any, dict[str, Any]]:
        """Obtain information about a status.

        Reference: https://docs.joinmastodon.org/methods/statuses/#get
        """
        return self.client.get(f"/api/v1/statuses/{status_id}")

    def status_context(
            self,
            status_id: str,
    ) -> Coroutine[Any, Any, dict[str, Any]]:
        """View statuses above and below this status in the thread.

        Reference: https://docs.joinmastodon.org/methods/statuses/#context
        """
        return self.client.get(f"/api/v1/statuses/{status_id}/context")

    def account_lookup(
            self,
            acct: str,
    ) -> Coroutine[Any, Any, dict[str, Any]]:
        """Quickly lookup a username to see if it is available.

        Skips WebFinger resolution.

        Reference: https://docs.joinmastodon.org/methods/accounts/#lookup
        """
        return self.client.get("/api/v1/accounts/lookup", params={"acct": acct})

    async def account_statuses(
            self,
            account_id: str,
            only_media: bool = False,
            pinned: bool = False,
            exclude_replies: bool = False,
            exclude_reblogs: bool = False,
            tagged: str | None = None,
            max_id: str | None = None,
            min_id: str | None = None,
            since_id: str | None = None,
            limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Statuses posted to the given account.

        Reference: https://docs.joinmastodon.org/methods/accounts/#statuses
        """
        params = {}
        if only_media:
            params["only_media"] = only_media
        if pinned:
            params["pinned"] = pinned
        if exclude_replies:
            params["exclude_replies"] = exclude_replies
        if exclude_reblogs:
            params["exclude_reblogs"] = exclude_reblogs
        if tagged:
            params["tagged"] = tagged
        if max_id:
            params["max_id"] = max_id
        if min_id:
            params["min_id"] = min_id
        if since_id:
            params["since_id"] = since_id
        if limit:
            params["limit"] = limit

        status_json = await self.client.get(
            f"/api/v1/accounts/{account_id}/statuses", params=params)
        status_list = status_json.get("list")
        if status_list:
            return status_list
        return []

    def account_verify_credentials(
        self,
    ) -> Coroutine[Any, Any, dict[str, Any]]:
        """Test to make sure that the user token works.

        Reference: https://docs.joinmastodon.org/methods/accounts/#verify_credentials
        """
        return self.client.get("/api/v1/accounts/verify_credentials")

    async def notifications(  # noqa: PLR0913
            self,
            max_id: str | None = None,
            since_id: str | None = None,
            min_id: str | None = None,
            limit: int | None = None,
            types: list[str] | None = None,
            exclude_types: list[str] | None = None,
            account_id: str | None = None,
    ) -> dict[str, Any]:
        """Notifications concerning the user.

        This API returns Link headers containing links to the next/previous page.
        However, the links can also be constructed dynamically using query params
        and id values.

        Reference: https://docs.joinmastodon.org/methods/notifications/#get
        """
        params = {}
        if max_id:
            params["max_id"] = max_id
        if since_id:
            params["since_id"] = since_id
        if min_id:
            params["min_id"] = min_id
        if limit:
            params["limit"] = limit
        if types:
            params["types"] = types
        if exclude_types:
            params["exclude_types"] = exclude_types
        if account_id:
            params["account_id"] = account_id
        return await self.client.get(
            "/api/v1/notifications", params=params)

    def bookmarks(
            self,
            max_id: str | None = None,
            since_id: str | None = None,
            min_id: str | None = None,
            limit: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any]]:
        """Statuses the user has bookmarked.

        Reference: https://docs.joinmastodon.org/methods/bookmarks/#get
        """
        params = {}
        if max_id:
            params["max_id"] = max_id
        if since_id:
            params["since_id"] = since_id
        if min_id:
            params["min_id"] = min_id
        if limit:
            params["limit"] = limit
        return self.client.get("/api/v1/bookmarks", params=params)

    def follow_requests(
            self,
            max_id: str | None = None,
            since_id: str | None = None,
            limit: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any]]:
        """Follow requests the user has received.

        Reference: https://docs.joinmastodon.org/methods/follow_requests/#get
        """
        params = {}
        if max_id:
            params["max_id"] = max_id
        if since_id:
            params["since_id"] = since_id
        if limit:
            params["limit"] = limit
        return self.client.get("/api/v1/follow_requests", params=params)

    def search_v2(  # noqa: PLR0913
            self,
            q: str,
            search_type: str | None = None,
            resolve: bool = False,
            following: bool = False,
            account_id: str | None = None,
            exclude_unreviewed: bool = False,
            max_id: str | None = None,
            min_id: str | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any]]:
        """Perform a search.

        Reference: https://docs.joinmastodon.org/methods/search/#v2
        """
        params = {"q": q}
        if search_type:
            params["type"] = search_type
        if resolve:
            params["resolve"] = str(resolve)
        if following:
            params["following"] = str(following)
        if account_id:
            params["account_id"] = account_id
        if exclude_unreviewed:
            params["exclude_unreviewed"] = str(exclude_unreviewed)
        if max_id:
            params["max_id"] = max_id
        if min_id:
            params["min_id"] = min_id
        if limit:
            params["limit"] = str(limit)
        if offset:
            params["offset"] = str(offset)
        return self.client.get("/api/v2/search", params=params)

    def admin_accounts_v2(
            self,
            origin: str | None = None,
            status: str | None = None,
            permissions: str | None = None,
            role_ids: list[str] | None = None,
            invited_by: str | None = None,
            username: str | None = None,
            display_name: str | None = None,
            by_domain: str | None = None,
            email: str | None = None,
            ip: str | None = None,
            max_id: str | None = None,
            since_id: str | None = None,
            min_id: str | None = None,
            limit: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any]]:
        """View all accounts.

        View all accounts, optionally matching certain criteria for filtering,
        up to 100 at a time. Pagination may be done with the HTTP Link header
        in the response. See Paginating through API responses for more information.

        Reference: https://docs.joinmastodon.org/methods/admin/accounts/#v2
        """
        params = {}
        if origin:
            params["origin"] = origin
        if status:
            params["status"] = status
        if permissions:
            params["permissions"] = permissions
        if role_ids:
            params["role_ids"] = role_ids
        if invited_by:
            params["invited_by"] = invited_by
        if username:
            params["username"] = username
        if display_name:
            params["display_name"] = display_name
        if by_domain:
            params["by_domain"] = by_domain
        if email:
            params["email"] = email
        if ip:
            params["ip"] = ip
        if max_id:
            params["max_id"] = max_id
        if since_id:
            params["since_id"] = since_id
        if min_id:
            params["min_id"] = min_id
        if limit:
            params["limit"] = limit
        return self.client.get("/api/v2/admin/accounts", params=params)

    def fetch_next(self, previous_page: dict[str, Any],
        ) -> Coroutine[Any, Any, dict[str, Any]]:
        """Fetch the next page of results.

        Reference: https://docs.joinmastodon.org/api/guidelines/#pagination
        """
        return self.client.get(previous_page["_pagination_next"])

