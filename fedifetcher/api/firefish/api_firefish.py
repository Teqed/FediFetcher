"""Firefish API functions."""
from argparse import Namespace
import asyncio
import logging
from typing import Any, ClassVar, Literal
from urllib.parse import urlparse

import aiohttp

from fedifetcher.api.firefish.api_firefish_types import Note, UserDetailedNotMe
from fedifetcher.api.mastodon import api_mastodon
from fedifetcher.api.mastodon.api_mastodon_types import Status
from fedifetcher.api.postgresql.postgresql import PostgreSQLUpdater
from fedifetcher.helpers.helpers import Response


class FirefishClient:
    """A class representing a Firefish instance."""

    def __init__(self,
                access_token : str | None,
                api_base_url : str,
                client : aiohttp.ClientSession) -> None:
        """Initialize a Firefish object."""
        self.access_token = access_token
        self.api_base_url = api_base_url
        self.client = client

    async def post(self,
        endpoint : str, json : dict[str, Any] | None = None,
        ) -> dict | bool:
        """POST to the API."""
        try:
            async with self.client.post(
                f"https://{self.api_base_url}{endpoint}",
                json=json,
                headers={"Authorization": f"Bearer {self.access_token}"},
            ) as response:
                    return await self.handle_response_errors(response)
        except asyncio.TimeoutError:
            logging.warning(
                f"Timeout error with Mastodon API on server {self.api_base_url}.")
            return False

    async def handle_response_errors(self, response: aiohttp.ClientResponse,
            ) -> dict | bool:
        """Handle errors from the API."""
        if response.status == Response.OK:
            body = await response.json()
            if body:
                return body
            return True
        if response.status == Response.BAD_REQUEST:
            logging.error(
                f"Error with Firefish API on server {self.api_base_url}. "
                f"400 Client error: {response}",
            )
        elif response.status == Response.UNAUTHORIZED:
            logging.error(
                f"Error with Firefish API on server {self.api_base_url}. "
                f"401 Authentication error: {response}",
            )
        elif response.status == Response.FORBIDDEN:
            logging.error(
                f"Error with Firefish API on server {self.api_base_url}. "
                f"403 Forbidden error: {response}",
            )
        elif response.status == Response.TEAPOT:
            logging.error(
                f"Error with Firefish API on server {self.api_base_url}. "
                f"418 I'm Calc: {response}",
            )
        elif response.status == Response.TOO_MANY_REQUESTS:
            logging.error(
                f"Error with Firefish API on server {self.api_base_url}. "
                f"429 Too many requests: {response}",
            )
        elif response.status == Response.INTERNAL_SERVER_ERROR:
            logging.warning(
                f"Error with Firefish API on server {self.api_base_url}. "
                f"500 Internal server error: {response}",
            )
        else:
            logging.error(
                f"Error with Firefish API on server {self.api_base_url}. "
                f"The server encountered an error: {response}",
            )
        return False

    async def ap_get(self, uri: str) -> bool:
        """POST to the API to do a ActivityPub get from a remote server.

        Args:
        ----
        uri (str): The URI of the object to get.

        Returns:
        -------
        bool: True if response status was 200, False otherwise.
        """
        if "/@" in uri:
            uri_parts = uri.split("/")
            base_url = urlparse(uri).netloc
            user_name = uri_parts[3][1:]  # remove "@" from username
            status_id = uri_parts[4]
            uri = f"https://{base_url}/users/{user_name}/statuses/{status_id}"

        result = await self.post("/api/ap/get", json={"uri": uri})
        if result:
            return True
        logging.warning(f"Could not get {uri} from {self.api_base_url}")
        return False

    async def ap_show(self, uri: str) -> tuple[str, (UserDetailedNotMe | Note)] | bool:
        """POST to the API to do a ActivityPub show from a remote server.

        Args:
        ----
        uri (str): The URI of the object to show.

        Returns:
        -------
        tuple[str, UserDetailedNotMe]: The type of the object, and the object \
            itself.
        """
        shown_object = await self.post("/api/ap/show", json={"uri": uri})
        if shown_object and isinstance(shown_object, dict):
            if shown_object["type"] == "Note":
                return (shown_object["type"], Note(**shown_object["object"]))
            if shown_object["type"] == "User":
                return (shown_object["type"], UserDetailedNotMe(
                    **shown_object["object"]))
        return False


    async def notes_show(self, note_id: str) -> Note | Literal[False]:
        """POST to the API to do a notes show from a remote server.

        Args:
        ----
        note_id (str): The ID of the note to show.

        Returns:
        -------
        Note: The object itself.
        """
        shown_object = await self.post("/api/notes/show", json={"noteId": note_id})
        if shown_object and isinstance(shown_object, dict):
            return Note(**shown_object)
        return False

class Firefish:
    """A class representing a Firefish instance."""

    clients : ClassVar[dict[str, FirefishClient]] = {}
    def __init__(self, server: str, token: str | None = None,
            pgupdater: PostgreSQLUpdater | None = None) -> None:
        """Initialize a Firefish object."""
        self.server = server
        self.token = token
        self.pgupdater = pgupdater
        if server not in Firefish.clients or (
            token is not None and Firefish.clients[server].access_token is None):
            msg = f"Creating Firefish session for {server}"
            logging.info(f"\033[1;33m{msg}\033[0m")
            if token:
                msg = "Using provided token"
                logging.info(f"\033[1;33m{msg}\033[0m")

            client = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60),
                headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 +https://github.com/Teqed Meowstodon/1.0.0",  # noqa: E501
            })

            Firefish.clients[server] = FirefishClient(
                access_token=token if token else None,
                api_base_url=server,
                client=client,
            )
        self.client = Firefish.clients[server]

    async def add_context_url(
            self,
            url : str,
            semaphore : asyncio.Semaphore | None = None,
            ) -> Note | UserDetailedNotMe | bool:
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
        if semaphore is None:
            semaphore = asyncio.Semaphore(1)
        async with semaphore:
            uri = url
            if (url.find("/@") != -1):
                uri_parts = url.split("/")
                base_url = urlparse(url).netloc
                user_name = uri_parts[3][1:]  # remove "@" from username
                status_id = uri_parts[4]
                uri = f"https://{base_url}/users/{user_name}/statuses/{status_id}"
            logging.debug(f"Adding {uri} to {self.server}")
            response = await self.client.ap_show(uri)
            logging.debug(f"Got {response} for {uri} from {self.server}")
            if response and not isinstance(response, bool):
                response_body = response[1]
                if response[0] == "Note" and isinstance(response_body, Note):
                    return response_body
                if response[0] == "User" and isinstance(
                        response_body, UserDetailedNotMe):
                    return response_body
            return False

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
        if self.pgupdater is None:
            logging.error("No PostgreSQLUpdater instance provided")
            return None
        cached_status = self.pgupdater.get_from_cache(url)
        if cached_status:
            status_id = cached_status.get("id")
            if status_id is not None:
                return status_id
        msg = f"Fetching status id for {url} from {self.server}"
        logging.info(f"\033[1;33m{msg}\033[0m")
        result = await self.add_context_url(url)
        if result:
            status_id = result.get("id") if isinstance(result, Note) else None
            logging.debug(f"Got status id {status_id} for {url} from {self.server}")
            status = self.pgupdater.get_from_cache(url)
            status_id = status.get("id") if status else None
            if status_id:
                logging.info(f"Got status id {status_id} for {url} from {self.server}")
                return str(status_id)
            logging.error(
                f"Something went wrong fetching: {url} from {self.server} , \
    did not match {result}")
        logging.debug(result)
        logging.warning(f"Status id for {url} not found")
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
        max_concurrent_tasks = 10
        semaphore = asyncio.Semaphore(max_concurrent_tasks)
        promises : list[tuple[str, asyncio.Task[Note | UserDetailedNotMe | bool]]] = []
        for url in urls:
            cached_status = cached_statuses.get(url)
            if cached_status:
                status_id = cached_status.get("id")
                if status_id is not None:
                    status_ids[url] = status_id
                    continue
            msg = f"Fetching status id for {url} from {self.server}"
            logging.info(f"\033[1;33m{msg}\033[0m")
            promises.append((url, asyncio.ensure_future(
                self.add_context_url(url, semaphore))))
        await asyncio.gather(*[promise for _, promise in promises])
        for url, result in promises:
            logging.debug(f"Got {result} for {url} from {self.server}")
            _result = result.result()
            if isinstance(_result, dict | Status):
                if _result.get("url") == url:
                    status = self.pgupdater.get_from_cache(url)
                    status_id = status.get("id") if status else None
                    status_ids[url] = status_id
                    logging.info(
                        f"Got status id {status_id} for {url} from {self.server}")
                    continue
                logging.error(
                    f"Something went wrong fetching: {url} from {self.server} , \
    did not match {_result.get('url')}")
                logging.debug(_result)
            elif _result is False:
                logging.warning(f"Failed to get status id for {url} on {self.server}")
            logging.error(f"Status id for {url} not found")
        return status_ids

    async def get_toot_context(
            self,
            server: str, toot_id: str, token: str | None,
            ) -> list[str]:
        """Get the URLs of the context toots of the given toot asynchronously."""
        if self.pgupdater is None:
            logging.error("No PostgreSQLUpdater instance provided")
            return []
        # Get the context of a toot
        context = await api_mastodon.Mastodon(
            server=server, token=token).status_context(status_id=toot_id)
        # List of status URLs
        ancestors = context.get("ancestors") or []
        descendants = context.get("descendants") or []
        context_statuses = list(ancestors + descendants)
        # Sort by server
        context_statuses.sort(key=lambda status: status["url"].split("/")[2])
        context_statuses_url_list = [status["url"] for status in context_statuses]
        home_status_list: dict[str, str] = await self.get_home_status_id_from_url_list(
            context_statuses_url_list)
        for status in context_statuses:
            home_status_id = home_status_list.get(status["url"])
            if home_status_id:
                self.pgupdater.queue_status_update(
                    home_status_id,
                    status.get("reblogs_count"), status.get("favourites_count"))
        # Commit status updates
        self.pgupdater.commit_status_updates()
        return [status["url"] for status in context_statuses]
