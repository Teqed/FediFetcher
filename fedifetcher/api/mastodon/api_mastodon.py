"""Mastodon API functions."""
import ast
import asyncio
import logging
from collections.abc import Coroutine, Iterable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar, cast

import aiohttp

from fedifetcher.api.mastodon.api_mastodon_types import Status
from fedifetcher.api.postgresql import PostgreSQLUpdater
from fedifetcher.helpers import helpers
from fedifetcher.helpers.helpers import Response


class MastodonClient:
    """A class representing a Mastodon client."""

    def __init__(self,
                    api_base_url: str,
                    client_session: aiohttp.ClientSession,
                    token: str | None = None,
                    pgupdater: PostgreSQLUpdater | None = None,
                    ) -> None:
            """Initialize the Mastodon client."""
            self.api_base_url = api_base_url
            self.token = token
            self.client_session = client_session
            self.pgupdater = pgupdater

    async def get(self,
        endpoint: str, params: dict | None = None, tries: int = 0,
        semaphore: asyncio.Semaphore | None = None) -> dict[str, Any]:
        """Perform a GET request to the Mastodon server."""
        if semaphore is None:
            semaphore = asyncio.Semaphore(1)
        async with semaphore:
            try:
                url = f"https://{self.api_base_url}{endpoint}"
                logging.debug(f"Getting {url} with {params}")
                async with self.client_session.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.token}",
                    },
                    params=params,
                ) as response:
                    logging.debug(f"Got {url} with {params} status {response.status}")
                    if response.status == Response.TOO_MANY_REQUESTS:
                        mastodon_ratelimit_reset_timer_in_minutes = 5
                        if tries > mastodon_ratelimit_reset_timer_in_minutes:
                            logging.error(
                            f"Error with Mastodon API on server {self.api_base_url}. "
                            f"Too many requests: {response}",
                            )
                            return {}
                        logging.warning(
                            f"Too many requests to {self.api_base_url}. "
                            f"Waiting 60 seconds before trying again.",
                        )
                        await asyncio.sleep(60)
                        return await self.get(
                            endpoint=endpoint, params=params, tries=tries + 1)
                    return await self.handle_response_errors(response)
            except asyncio.TimeoutError:
                logging.warning(
                    f"Timeout error with Mastodon API on server {self.api_base_url}.")
            except aiohttp.ClientConnectorSSLError:
                logging.warning(
                    f"SSL error with Mastodon API on server {self.api_base_url}.")
            except aiohttp.ClientConnectorError:
                logging.exception(
                f"Connection error with Mastodon API on server {self.api_base_url}.")
            except (aiohttp.ClientError):
                logging.exception(
                    f"Error with Mastodon API on server {self.api_base_url}.")
            except Exception:
                logging.exception(
                    f"Unknown error with Mastodon API on server {self.api_base_url}.")
            return {}

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
        if server not in Mastodon.clients or (
            token is not None and Mastodon.clients[server].token is None) or (
            pgupdater is not None and Mastodon.clients[server].pgupdater is None
            ):
            msg = f"Creating Mastodon client for {server}"
            logging.info(f"\033[1;33m{msg}\033[0m")
            if token:
                msg = "Using provided token"
                logging.info(f"\033[1;33m{msg}\033[0m")
            client = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60),
                headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 +https://github.com/Teqed Meowstodon/1.0.0",  # noqa: E501
            })

            Mastodon.clients[server] = MastodonClient(
                api_base_url=server if server else helpers.arguments.server,
                client_session=client,
                token=token,
                pgupdater=pgupdater,
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
        if self.client.api_base_url == helpers.arguments.server or \
                not self.client.api_base_url:
            account = await self.account_lookup(
                acct = f"{user}",
            )
            if not isinstance(account, bool):
                return account["id"]
        account_search = await self.account_lookup(
            acct = f"{user}",
        )
        if not isinstance(account_search, bool) \
            and account_search.get("username") == user:
            return account_search["id"]
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
        timeline_toots_dict = await self.timelines_home(limit=limit)
        if not (timeline_toots := timeline_toots_dict.get("list")):
            return []
        toots = cast(list[dict[str, str]], (
            timeline_toots))
        toots_result = toots.copy()
        number_of_toots_received = len(toots)
        while isinstance(toots, dict) and number_of_toots_received < limit and \
                timeline_toots_dict.get("_pagination_next"):
            toots_dict = await self.fetch_next(toots)
            if not (toots := toots_dict.get("list")):
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
        logging.debug(f"Getting active user IDs for {self.client.api_base_url}")
        logging.debug(f"Reply interval: {reply_interval_hours} hours")
        since = datetime.now(UTC) - timedelta(days=reply_interval_hours / 24 + 1)
        logging.debug(f"Since: {since}")
        local_accounts = (await self.admin_accounts_v2(
            origin="local",
            status="active",
        )).get("list")
        active_user_ids = []
        if local_accounts:
            logging.debug(f"Found {len(local_accounts)} accounts")
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
        logging.info(f"Getting posts for user {user_id} on {self.client.api_base_url}")
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
        if not self.client.pgupdater:
            return None
        try:
            all_statuses = await self.get_user_posts_from_id(user_id)
            if all_statuses:
                return [
                    toot
                    for toot in all_statuses
                    if toot["in_reply_to_id"]
                    and datetime.strptime(
                        toot["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ",
                    ).replace(tzinfo=UTC) > reply_since \
                    and self.client.pgupdater.get_from_cache(toot["url"]) is None
                ]
        except Exception:
            logging.exception(f"Error getting user posts for user {user_id}")
            raise
        return None

    async def get_toot_context(
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
        context = await self.status_context(status_id=toot_id)
        # List of status URLs
        ancestors = context.get("ancestors") or []
        descendants = context.get("descendants") or []
        context_statuses = list(ancestors + descendants)
        # Sort by server
        context_statuses.sort(key=lambda status: status["url"].split("/")[2])
        context_statuses_url_list = [status["url"] for status in context_statuses]
        home_status_list: dict[str, str] = \
            await Mastodon(home_server, home_token, _pgupdater,
                    ).get_home_status_id_from_url_list(context_statuses_url_list)
        for status in context_statuses:
            home_status_id = home_status_list.get(status["url"])
            if home_status_id:
                _pgupdater.queue_status_update(
                    home_status_id,
                    status.get("reblogs_count"), status.get("favourites_count"))
        # Commit status updates
        _pgupdater.commit_status_updates()
        return [status["url"] for status in context_statuses]

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
            notification_id=notification_id,
            max_id=max_id,
            since_id=since_id,
            min_id=min_id,
            limit=limit,
            types=types,
            exclude_types=exclude_types,
            account_id=account_id,
        )
        if not (notifications := notifications_dict.get("list")):
            return []
        number_of_notifications_received = len(notifications)
        notifications_result = notifications.copy()
        while notifications \
                and number_of_notifications_received < limit \
                    and notifications_dict.get("_pagination_next"):
            more_notifications_dict = await self.fetch_next(notifications_dict)
            if not (more_notifications := more_notifications_dict.get("list")):
                break
            number_of_notifications_received += len(more_notifications)
            notifications_result.extend(more_notifications)
        return cast(list[dict[str, str]], notifications_result)

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
        bookmarks_dict = await self.bookmarks(limit=limit)
        if not (bookmarks := bookmarks_dict.get("list")):
            return []
        number_of_bookmarks_received = len(bookmarks)
        bookmarks_result = bookmarks.copy()
        while bookmarks \
                and number_of_bookmarks_received < limit \
                    and bookmarks_dict.get("_pagination_next"):
            more_bookmarks_dict = await self.fetch_next(bookmarks_dict)
            if not (more_bookmarks := more_bookmarks_dict.get("list")):
                break
            number_of_bookmarks_received += len(more_bookmarks)
            bookmarks_result.extend(more_bookmarks)
        return cast(list[dict[str, str]], bookmarks_result)

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
        favourites_dict = await self.favourites(limit=limit)
        if not (favourites := favourites_dict.get("list")):
            return []
        number_of_favourites_received = len(favourites)
        favourites_result = favourites.copy()
        if favourites and favourites_dict:
            while number_of_favourites_received < limit \
                    and favourites_dict.get("_pagination_next"):
                more_favourites_dict = await self.fetch_next(favourites_dict)
                if not (more_favourites := more_favourites_dict.get("list")):
                    break
                number_of_favourites_received += len(more_favourites)
                favourites_result.extend(more_favourites)
        return cast(list[dict[str, str]], favourites_result)

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
        follow_requests_dict = await self.follow_requests(limit=limit)
        if not (follow_requests := follow_requests_dict.get("list")):
            return []
        number_of_follow_requests_received = len(follow_requests)
        follow_requests_result = follow_requests.copy()
        while follow_requests \
                and number_of_follow_requests_received < limit \
                    and follow_requests_dict.get("_pagination_next"):
            more_follow_requests = await self.fetch_next(follow_requests_dict)
            if not more_follow_requests:
                break
            number_of_follow_requests_received += len(more_follow_requests)
            follow_requests_result.extend(more_follow_requests)
        return cast(list[dict[str, str]], follow_requests_result)

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
        followers_dict = await self.account_followers(account_id=user_id, limit=limit)
        if not (followers := followers_dict.get("list")):
            return []
        number_of_followers_received = len(followers)
        followers_result = followers.copy()
        while followers \
                and number_of_followers_received < limit \
                    and followers_dict.get("_pagination_next"):
            more_followers_dict = await self.fetch_next(followers_dict)
            if not (more_followers := more_followers_dict.get("list")):
                break
            number_of_followers_received += len(more_followers)
            followers_result.extend(more_followers)
        return cast(list[dict[str, str]], followers_result)

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
        following_dict = await self.account_following(account_id=user_id, limit=limit)
        if not (following := following_dict.get("list")):
            return []
        number_of_following_received = len(following)
        following_result = following.copy()
        while following \
                and number_of_following_received < limit \
                    and following_dict.get("_pagination_next"):
            more_following_dict = await self.fetch_next(following_dict)
            if not (more_following := more_following_dict.get("list")):
                break
            number_of_following_received += len(more_following)
            following_result.extend(more_following)
        return cast(list[dict[str, str]], following_result)

    async def add_context_url(
            self,
            url : str,
            semaphore: asyncio.Semaphore | None = None,
            ) -> Status | bool:
        """Add the given toot URL to the server.

        Args:
        ----
        url: The URL of the toot to add.
        semaphore: The semaphore to use for the request.

        Returns:
        -------
        dict[str, str] | bool: The status of the request, or False if the \
            request fails.
        """
        if semaphore is None:
            semaphore = asyncio.Semaphore(1)
        async with semaphore:
            logging.debug(f"Adding context url {url} to {self.client.api_base_url}")
            if not self.client.pgupdater:
                logging.debug(f"pgupdater not set for {self.client.api_base_url}")
                return False
            try:
                result = await self.search_v2(
                    q = url,
                    resolve = True,
                )
            except Exception:
                logging.exception(
                    f"Error adding context url {url} to {self.client.api_base_url}")
                return False
            if (statuses := result.get("statuses")):
                for _status in statuses:
                    if _status.get("url") == url:
                        self.client.pgupdater.cache_status(_status)
                        return _status
                    if _status.get("uri") == url:
                        self.client.pgupdater.cache_status(_status)
                        return _status
                    logging.debug(f"{url} did not match {_status.get('url')}")
            logging.debug(
                f"Could not find status for {url} on {self.client.api_base_url}")
            return False

    async def get_trending_posts(
            self,
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
        async def _get_trending_posts(
                offset: int = 0,
        ) -> list[dict[str, str]]:
            """Get a page of trending posts and return it."""
            getting_trending_posts_dict = await self.trending_statuses(
                                                limit=40, offset=offset)
            if not (getting_trending_posts := getting_trending_posts_dict.get("list")):
                return []
            return cast(list[dict[str, str]], getting_trending_posts)

        msg = f"Getting {limit} trending posts for {self.client.api_base_url}"
        logging.info(f"\033[1m{msg}\033[0m")
        got_trending_posts: list[dict[str, str]] = []
        try:
            got_trending_posts = await _get_trending_posts(0)
        except Exception:
            logging.exception(
                f"Error getting trending posts for {self.client.api_base_url}")
            return []
        logging.info(
        f"Got {len(got_trending_posts)} trending posts for {self.client.api_base_url}")
        trending_posts: list[dict[str, str]] = []
        trending_posts.extend(got_trending_posts)
        a_page = 40
        if limit > a_page and len(got_trending_posts) == a_page:
            while len(trending_posts) < limit:
                try:
                    got_trending_posts = await _get_trending_posts(
                                                        len(trending_posts))
                except Exception:
                    logging.exception(
                        f"Error getting trending posts for {self.client.api_base_url}")
                    break
                old_length = len(trending_posts)
                trending_posts.extend(got_trending_posts)
                new_length = len(trending_posts)
                logging.info(
                f"Got {new_length} trending posts for {self.client.api_base_url} ...")
                if (len(got_trending_posts) < a_page) or (old_length == new_length):
                    break

        logging.info(
    f"Found {len(trending_posts)} trending posts total for {self.client.api_base_url}")
        return trending_posts

    async def get_home_status_id_from_url(
            self,
            url: str,
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
        if not self.client.pgupdater:
            return None
        cached_status = self.client.pgupdater.get_from_cache(url)
        if cached_status:
            status_id = cached_status.get("id")
            if status_id is not None:
                return status_id
        msg = f"Fetching status id for {url} from {self.client.api_base_url}"
        logging.info(f"\033[1;33m{msg}\033[0m")
        result = await self.add_context_url(url)
        logging.debug(f"Result: {result}")
        if not isinstance(result, bool):
            if result.get("url") == url:
                status = self.client.pgupdater.get_from_cache(url)
                status_id = status.get("id") if status else None
                logging.info(
                f"Got status id {status_id} for {url} from {self.client.api_base_url}")
                return str(status_id)
            logging.error(
            f"Something went wrong fetching: {url} from {self.client.api_base_url} , \
did not match {result.get('url')}")
            logging.debug(result)
        elif result is False:
            logging.warning(
                f"Failed to get status id for {url} on {self.client.api_base_url}")
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
        if not self.client.pgupdater:
            return {}
        status_ids = {}
        cached_statuses: dict[str, Status | None] = \
            self.client.pgupdater.get_dict_from_cache(urls)
        max_concurrent_tasks = 10
        semaphore = asyncio.Semaphore(max_concurrent_tasks)
        promises : list[tuple[str, asyncio.Task[Status | bool]]] = []
        for url in urls:
            cached_status = cached_statuses.get(url)
            if cached_status:
                status_id = cached_status.get("id")
                if status_id is not None:
                    status_ids[url] = status_id
                    continue
            msg = f"Fetching status id for {url} from {self.client.api_base_url}"
            logging.info(f"\033[1;33m{msg}\033[0m")
            promises.append((url, asyncio.ensure_future(
                self.add_context_url(url, semaphore))))
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
                f"Got status id {status_id} for {url} from {self.client.api_base_url}")
                    continue
                logging.error(
            f"Something went wrong fetching: {url} from {self.client.api_base_url} , \
did not match {_result.get('url')}")
                logging.debug(_result)
            elif _result is False:
                logging.warning(
                f"Failed to get status id for {url} on {self.client.api_base_url}")
            logging.error(f"Status id for {url} not found")
        return status_ids

    def get_status_by_id(
            self,
            status_id : str,
            semaphore: asyncio.Semaphore | None = None,
            ) -> Coroutine[Any, Any, dict[str, Any] | Status]:
        """Get the status from a toot URL.

        Args:
        ----
        status_id (str): The ID of the toot to get the status of.
        semaphoe (asyncio.Semaphore): The semaphore to use for the request.

        Returns:
        -------
        dict[str, str] | None: The status of the toot, or None if the toot is not found.
        """
        return self.status(status_id, semaphore=semaphore)

    def status(
            self,
            status_id: str,
            semaphore: asyncio.Semaphore | None = None,
        ) -> Coroutine[Any, Any, dict[str, Any] | Status]:
        """Obtain information about a status.

        Reference: https://docs.joinmastodon.org/methods/statuses/#get
        """
        return self.client.get(f"/api/v1/statuses/{status_id}", semaphore=semaphore)

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

    def notifications(  # noqa: PLR0913
            self,
            notification_id : str | None = None,
            max_id: str | None = None,
            since_id: str | None = None,
            min_id: str | None = None,
            limit: int | None = None,
            types: list[str] | None = None,
            exclude_types: list[str] | None = None,
            account_id: str | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any]]:
        """Notifications concerning the user.

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
        if notification_id:
            return self.client.get(
                f"/api/v1/notifications/{notification_id}")
        return self.client.get(
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

    def favourites(
            self,
            max_id: str | None = None,
            min_id: str | None = None,
            since_id: str | None = None,
            limit: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any]]:
        """Statuses the user has favourited.

        Reference: https://docs.joinmastodon.org/methods/favourites/#get
        """
        params = {}
        if max_id:
            params["max_id"] = max_id
        if min_id:
            params["min_id"] = min_id
        if since_id:
            params["since_id"] = since_id
        if limit:
            params["limit"] = limit
        return self.client.get("/api/v1/favourites", params=params)

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

    def account_followers(
            self,
            account_id: str,
            max_id: str | None = None,
            since_id: str | None = None,
            limit: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any]]:
        """Accounts which follow the given account.

        If network is not hidden by the account owner.

        Reference: https://docs.joinmastodon.org/methods/accounts/#followers
        """
        params = {}
        if max_id:
            params["max_id"] = max_id
        if since_id:
            params["since_id"] = since_id
        if limit:
            params["limit"] = limit
        return self.client.get(
            f"/api/v1/accounts/{account_id}/followers", params=params)

    def account_following(
            self,
            account_id: str,
            max_id: str | None = None,
            since_id: str | None = None,
            limit: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any]]:
        """Accounts which the given account is following.

        If network is not hidden by the account owner.

        Reference: https://docs.joinmastodon.org/methods/accounts/#following
        """
        params = {}
        if max_id:
            params["max_id"] = max_id
        if since_id:
            params["since_id"] = since_id
        if limit:
            params["limit"] = limit
        return self.client.get(
            f"/api/v1/accounts/{account_id}/following", params=params)

    def trending_statuses(
            self,
            limit: int | None = None,
            offset: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any]]:
        """Get trending statuses.

        Reference: https://docs.joinmastodon.org/methods/trends/#statuses
        """
        params = {}
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
        return self.client.get("/api/v1/trends/statuses", params=params)

    def timelines_home(
            self,
            max_id: str | None = None,
            since_id: str | None = None,
            min_id: str | None = None,
            limit: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any]]:
        """Home timeline.

        Reference: https://docs.joinmastodon.org/methods/timelines/#home
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
        return self.client.get("/api/v1/timelines/home", params=params)

    def timelines_public(
            self,
            local: bool = False,
            remote: bool = False,
            only_media: bool = False,
            max_id: str | None = None,
            since_id: str | None = None,
            min_id: str | None = None,
            limit: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any]]:
        """Public timeline.

        Reference: https://docs.joinmastodon.org/methods/timelines/#public
        """
        params = {}
        if local:
            params["local"] = local
        if only_media:
            params["only_media"] = only_media
        if max_id:
            params["max_id"] = max_id
        if since_id:
            params["since_id"] = since_id
        if min_id:
            params["min_id"] = min_id
        if limit:
            params["limit"] = limit
        return self.client.get("/api/v1/timelines/public", params=params)

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
