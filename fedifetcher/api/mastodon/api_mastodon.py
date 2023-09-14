"""Mastodon API functions."""
import ast
import asyncio
import logging
from collections.abc import Coroutine, Iterable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar, cast

import aiohttp

from fedifetcher.api.api import API
from fedifetcher.api.client import HttpMethod
from fedifetcher.api.mastodon.accounts import Accounts
from fedifetcher.api.mastodon.admin import Admin
from fedifetcher.api.mastodon.api_mastodon_types import Status
from fedifetcher.api.mastodon.favourites import Favourites
from fedifetcher.api.mastodon.notifications import Notifications
from fedifetcher.api.mastodon.relationships import Relationships
from fedifetcher.api.mastodon.search import Search
from fedifetcher.api.mastodon.statuses import Statuses
from fedifetcher.api.mastodon.timeline import Timeline
from fedifetcher.api.mastodon.trends import Trends
from fedifetcher.api.mastodon.utility import Utility
from fedifetcher.api.postgresql import PostgreSQLUpdater


class Mastodon(API, Statuses, Accounts, Notifications, Favourites, Timeline, Trends,
            Admin, Search, Relationships, Utility,
            ):
    """A class representing a Mastodon instance."""

    clients: ClassVar[dict[str, HttpMethod]] = {}

    def __init__(
        self,
        server: str,
        token: str | None = None,
        pgupdater: PostgreSQLUpdater | None = None,
    ) -> None:
        """Initialize the Mastodon instance."""
        if (
            server not in Mastodon.clients
            or (token is not None and Mastodon.clients[server].token is None)
            or (pgupdater is not None and Mastodon.clients[server].pgupdater is None)
        ):
            msg = f"Creating Mastodon client for {server}"
            logging.info(f"\033[1;33m{msg}\033[0m")
            if token:
                msg = "Using provided token"
                logging.info(f"\033[1;33m{msg}\033[0m")
            client_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 +https://github.com/Teqed Meowstodon/1.0.0",  # noqa: E501
                },
            )

            Mastodon.clients[server] = HttpMethod(
                api_base_url=server,
                session=client_session,
                token=token,
                pgupdater=pgupdater,
            )
        self.client = Mastodon.clients[server]

    async def get_user_id(
        self,
        user: str,
    ) -> str | None:
        """Get the user id from the server using a username.

        This function retrieves the user id from the server by \
            performing a search based on the provided username.

        Args:
        ----
        user (str): The username for which to retrieve the user id.

        Returns:
        -------
        str | None: The user id if found, or None if the user is not found.
        """
        account_search = await self.account_lookup(
            self.client,
            acct=f"{user}",
        )
        if account_search and account_search.get("username") == user:
            return account_search["id"]
        return None

    async def get(
            self,
            uri: str,
            semaphore: asyncio.Semaphore | None = None,
        ) -> Status | bool:
        """Add the given toot URL to the server.

        Args:
        ----
        uri: The URL of the toot to add.
        semaphore: The semaphore to use for the request.

        Returns:
        -------
        dict[str, str] | bool: The status of the request, or False if the \
            request fails.
        """
        if semaphore is None:
            semaphore = asyncio.Semaphore(1)
        async with semaphore:
            logging.debug(f"Adding context url {uri} to {self.client.api_base_url}")
            try:
                cached_status = self.client.pgupdater.get_from_cache(uri) if self.client.pgupdater else None
                if cached_status:
                    msg = f"Found cached status id {cached_status.get('id')} for {uri} on {self.client.api_base_url}"
                    logging.info(f"\033[1;33m{msg}\033[0m")
                    result = { "statuses": [cached_status] }
                else:
                    msg = f"Fetching status id for {uri} from {self.client.api_base_url}"
                    logging.info(f"\033[1;33m{msg}\033[0m")
                    result = await self.search_v2(
                        client=self.client,
                        q=uri,
                        resolve=True,
                    )
            except Exception:
                logging.exception(
                    f"Error adding context url {uri} to {self.client.api_base_url}",
                )
                return False
            if result and (statuses := result.get("statuses")):
                for _status in statuses:
                    if _status.get("url") == uri:
                        self.client.pgupdater.cache_status(_status) if self.client.pgupdater else None
                        return _status
                    if _status.get("uri") == uri:
                        self.client.pgupdater.cache_status(_status) if self.client.pgupdater else None
                        return _status
                    logging.debug(f"{uri} did not match {_status.get('url')}")
            elif result == {}:
                logging.debug(
                    f"Received empty results for {uri} on {self.client.api_base_url} ",
                    "The domain may be blocked.",
                )
                return False
            logging.debug(
                f"Could not find status for {uri} on {self.client.api_base_url}",
            )
            return False

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
        me = await self.account_verify_credentials(self.client)
        if me:
            return (me).get("id")
        return None

    async def get_ids_from_list(
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
        if not self.client.pgupdater:
            return {}
        status_ids = {}
        cached_statuses: dict[
            str,
            Status | None,
        ] = self.client.pgupdater.get_dict_from_cache(urls)
        max_concurrent_tasks = 10
        semaphore = asyncio.Semaphore(max_concurrent_tasks)
        promises: list[tuple[str, asyncio.Task[Status | bool]]] = []
        for url in urls:
            cached_status = cached_statuses.get(url)
            if cached_status:
                status_id = cached_status.get("id")
                if status_id is not None:
                    status_ids[url] = status_id
                    continue
            msg = f"Fetching status id for {url} from {self.client.api_base_url}"
            logging.info(f"\033[1;33m{msg}\033[0m")
            promises.append(
                (url, asyncio.ensure_future(self.get(url, semaphore))),
            )
        await asyncio.gather(*[promise for _, promise in promises])
        for url, task in promises:
            _result = task.result()
            logging.debug(_result)
            if not isinstance(_result, bool):
                if _result.get("url") == url:
                    status = self.client.pgupdater.get_from_cache(url)
                    status_id = status.get("id") if status else None
                    status_ids[url] = status_id
                    logging.info(
                        f"Got status id {status_id} for {url} from "
                        f"{self.client.api_base_url}",
                    )
                    continue
                logging.error(
                    f"Something went wrong fetching: {url} from "
                    f"{self.client.api_base_url} , did not match {_result.get('url')}",
                )
                logging.debug(_result)
            elif _result is False:
                logging.warning(
                    f"Failed to get status id for {url} on {self.client.api_base_url}",
                )
            logging.error(f"Status id for {url} not found")
        return status_ids

    def get_context(
        self,
        uri: str,
    ) -> Coroutine[Any, Any, list[str]] | type[NotImplementedError]:
        """Get the context of an object by URI."""
        logging.debug(f"Getting context for {uri} on {self.client.api_base_url}")
        return NotImplementedError

    def get_status_by_id(
        self,
        status_id: str,
        semaphore: asyncio.Semaphore | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any] | Status]:
        """Get the status from a toot URL.

        Args:
        ----
        status_id (str): The ID of the toot to get the status of.
        semaphore (asyncio.Semaphore): The semaphore to use for the request.

        Returns:
        -------
        dict[str, str] | None: The status of the toot, or None if the toot is not found.
        """
        return self.status(self.client, status_id, semaphore=semaphore)

    async def get_trending_statuses(
        self,
        limit: int = 40,
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

        async def _async_get_trending_posts(
            offset: int = 0,
        ) -> list[dict[str, str]]:
            """Get a page of trending posts and return it."""
            getting_trending_posts_dict = await self.trending_statuses(
                client=self.client,
                limit=40,
                offset=offset,
            )
            if not getting_trending_posts_dict or not (
                getting_trending_posts := getting_trending_posts_dict.get("list")
            ):
                return []
            return cast(list[dict[str, str]], getting_trending_posts)

        msg = f"Getting {limit} trending posts for {self.client.api_base_url}"
        logging.info(f"\033[1m{msg}\033[0m")
        got_trending_posts: list[dict[str, str]] = []
        try:
            got_trending_posts = await _async_get_trending_posts(0)
        except Exception:
            logging.exception(
                f"Error getting trending posts for {self.client.api_base_url}",
            )
            return []
        logging.info(
            f"Got {len(got_trending_posts)} trending posts for "
            f"{self.client.api_base_url}",
        )
        trending_posts: list[dict[str, str]] = []
        trending_posts.extend(got_trending_posts)
        a_page = 40
        if limit > a_page and len(got_trending_posts) == a_page:
            while len(trending_posts) < limit:
                try:
                    got_trending_posts = await _async_get_trending_posts(len(trending_posts))
                except Exception:
                    logging.exception(
                        f"Error getting trending posts for {self.client.api_base_url}",
                    )
                    break
                old_length = len(trending_posts)
                trending_posts.extend(got_trending_posts)
                new_length = len(trending_posts)
                logging.info(
                    f"Got {new_length} trending posts for "
                    f"{self.client.api_base_url} ...",
                )
                if (len(got_trending_posts) < a_page) or (old_length == new_length):
                    break

        logging.info(
            f"Found {len(trending_posts)} trending posts total for "
            f"{self.client.api_base_url}",
        )
        return trending_posts

    async def get_following(
        self,
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
        following_dict = await self.account_following(client=self.client, account_id=user_id, limit=limit)
        if not following_dict or not (following := following_dict.get("list")):
            return []
        number_of_following_received = len(following)
        following_result = following.copy()
        while (
            following
            and number_of_following_received < limit
            and following_dict.get("_pagination_next")
        ):
            more_following_dict = await self.fetch_next(self.client, following_dict)
            if not more_following_dict or not (
                more_following := more_following_dict.get("list")
            ):
                break
            number_of_following_received += len(more_following)
            following_result.extend(more_following)
        return cast(list[dict[str, str]], following_result)

    async def get_followers(
        self,
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
        followers_dict = await self.account_followers(client=self.client, account_id=user_id, limit=limit)
        if not followers_dict or not (followers := followers_dict.get("list")):
            return []
        number_of_followers_received = len(followers)
        followers_result = followers.copy()
        while (
            followers
            and number_of_followers_received < limit
            and followers_dict.get("_pagination_next")
        ):
            more_followers_dict = await self.fetch_next(self.client, followers_dict)
            if not more_followers_dict or not (
                more_followers := more_followers_dict.get("list")
            ):
                break
            number_of_followers_received += len(more_followers)
            followers_result.extend(more_followers)
        return cast(list[dict[str, str]], followers_result)

    async def get_follow_requests(
        self,
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
        follow_requests_dict = await self.follow_requests(client=self.client, limit=limit)
        if not follow_requests_dict or not (
            follow_requests := follow_requests_dict.get("list")
        ):
            return []
        number_of_follow_requests_received = len(follow_requests)
        follow_requests_result = follow_requests.copy()
        while (
            follow_requests
            and number_of_follow_requests_received < limit
            and follow_requests_dict.get("_pagination_next")
        ):
            more_follow_requests = await self.fetch_next(self.client, follow_requests_dict)
            if not more_follow_requests:
                break
            number_of_follow_requests_received += len(more_follow_requests)
            follow_requests_result.extend(more_follow_requests)
        return cast(list[dict[str, str]], follow_requests_result)

    async def get_favourites(
        self,
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
        favourites_dict = await self.favourites(client=self.client, limit=limit)
        if not favourites_dict or not (favourites := favourites_dict.get("list")):
            return []
        number_of_favourites_received = len(favourites)
        favourites_result = favourites.copy()
        if favourites and favourites_dict:
            while number_of_favourites_received < limit and favourites_dict.get(
                "_pagination_next",
            ):
                more_favourites_dict = await self.fetch_next(self.client, favourites_dict)
                if not more_favourites_dict or not (
                    more_favourites := more_favourites_dict.get("list")
                ):
                    break
                number_of_favourites_received += len(more_favourites)
                favourites_result.extend(more_favourites)
        return cast(list[dict[str, str]], favourites_result)

    async def get_bookmarks(
        self,
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
        bookmarks_dict = await self.bookmarks(client=self.client, limit=limit)
        if not bookmarks_dict or not (bookmarks := bookmarks_dict.get("list")):
            return []
        number_of_bookmarks_received = len(bookmarks)
        bookmarks_result = bookmarks.copy()
        while (
            bookmarks
            and number_of_bookmarks_received < limit
            and bookmarks_dict.get("_pagination_next")
        ):
            more_bookmarks_dict = await self.fetch_next(self.client, bookmarks_dict)
            if not more_bookmarks_dict or not (
                more_bookmarks := more_bookmarks_dict.get("list")
            ):
                break
            number_of_bookmarks_received += len(more_bookmarks)
            bookmarks_result.extend(more_bookmarks)
        return cast(list[dict[str, str]], bookmarks_result)

    async def get_notifications(
        self,
        notification_id: str | None = None,
        max_id: str | None = None,
        since_id: str | None = None,
        min_id: str | None = None,
        limit: int = 40,
        types: list[str] | None = None,
        exclude_types: list[str] | None = None,
        account_id: str | None = None,
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
        notifications_dict = await self.notifications(
            client=self.client,
            notification_id=notification_id,
            max_id=max_id,
            since_id=since_id,
            min_id=min_id,
            limit=limit,
            types=types,
            exclude_types=exclude_types,
            account_id=account_id,
        )
        if not notifications_dict or not (
            notifications := notifications_dict.get("list")
        ):
            return []
        number_of_notifications_received = len(notifications)
        notifications_result = notifications.copy()
        while (
            notifications
            and number_of_notifications_received < limit
            and notifications_dict.get("_pagination_next")
        ):
            more_notifications_dict = await self.fetch_next(self.client, notifications_dict)
            if not more_notifications_dict or not (
                more_notifications := more_notifications_dict.get("list")
            ):
                break
            number_of_notifications_received += len(more_notifications)
            notifications_result.extend(more_notifications)
        return cast(list[dict[str, str]], notifications_result)

    async def get_status_context(
        self,
        toot_id: str,
        home_server: str,
        home_token: str,
        _pgupdater: PostgreSQLUpdater,
    ) -> list[str]:
        """Get the URLs of the context toots of the given toot asynchronously."""
        if not _pgupdater:
            return []
        # Get the context of a toot
        context = await self.status_context(self.client, status_id=toot_id)
        if not context:
            return []
        # List of status URLs
        ancestors = context.get("ancestors") or []
        descendants = context.get("descendants") or []
        context_statuses = list(ancestors + descendants)
        # Sort by server
        context_statuses.sort(key=lambda status: status["url"].split("/")[2])
        context_statuses_url_list = [status["url"] for status in context_statuses]
        home_status_list: dict[str, str] = await Mastodon(
            home_server,
            home_token,
            _pgupdater,
        ).get_ids_from_list(context_statuses_url_list)
        for status in context_statuses:
            home_status_id = home_status_list.get(status["url"])
            if home_status_id:
                _pgupdater.queue_status_update(
                    home_status_id,
                    status.get("reblogs_count"),
                    status.get("favourites_count"),
                )
        # Commit status updates
        _pgupdater.commit_status_updates()
        return [status["url"] for status in context_statuses]

    async def get_user_statuses(
        self,
        user_id: str,
        reply_since: datetime | None = None,
    ) -> list[dict[str, str]] | None:
        """Get a list of posts from a user.

        Args:
        ----
        user_id (str): The user id of the user to get the posts from.
        reply_since (datetime): The datetime to get posts since, if only fetching \
            replies.

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
        if not reply_since:
            logging.info(
                f"Getting posts for user {user_id} on {self.client.api_base_url}")
            return await self.account_statuses(
                self.client,
                account_id=user_id,
                limit=40,
            )

        if not self.client.pgupdater:
            return None
        try:
            all_statuses = await self.get_user_statuses(user_id)
            if all_statuses:
                return [
                    toot
                    for toot in all_statuses
                    if toot["in_reply_to_id"]
                    and datetime.strptime(
                        toot["created_at"],
                        "%Y-%m-%dT%H:%M:%S.%fZ",
                    ).replace(tzinfo=UTC)
                    > reply_since
                    and self.client.pgupdater.get_from_cache(toot["url"]) is None
                ]
        except Exception:
            logging.exception(f"Error getting user posts for user {user_id}")
            raise
        return None

    async def get_home_timeline(
        self,
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
        timeline_toots_dict = await self.timelines_home(client=self.client, limit=limit)
        if not timeline_toots_dict or (
            timeline_toots := timeline_toots_dict.get("list")
        ):
            return []
        toots = cast(list[dict[str, str]], (timeline_toots))
        toots_result = toots.copy()
        number_of_toots_received = len(toots)
        while (
            isinstance(toots, dict)
            and number_of_toots_received < limit
            and timeline_toots_dict.get("_pagination_next")
        ):
            toots_dict = await self.fetch_next(self.client, toots)
            if not toots_dict or not (toots := toots_dict.get("list")):
                break
            number_of_toots_received += len(toots)
            toots_result.extend(toots)
        logging.info(f"Found {number_of_toots_received} posts in timeline")
        return toots_result


def filter_language(
    toots: Iterable[dict[str, str]],
    language: str,
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
    return filter(lambda toot: toot.get("language") == language, toots)
