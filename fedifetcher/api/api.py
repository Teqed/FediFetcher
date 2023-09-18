"""Interface for dependency injection of different APIs."""

import asyncio
from abc import ABCMeta, abstractmethod
from collections.abc import Coroutine
from datetime import datetime
from typing import Any

import aiohttp

from fedifetcher.api.client import HttpMethod


class ApiError(Exception):
    """Error raised when an API call fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialize the error."""
        super().__init__(message)
        self.status_code = status_code
class API(metaclass=ABCMeta):
    """Interface for dependency injection of different APIs."""

    client: HttpMethod

    @abstractmethod
    def __init__(
        self,
        server: str,
        token: str | None = None,
        pgupdater: Any | None = None,
        ) -> None:
        """Initialize the API."""
        raise NotImplementedError

    async def cleanup(self) -> None:
        await self.client.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        await self.cleanup()

    @abstractmethod
    def get(self, uri: str) -> Coroutine[Any, Any, dict]:
        """Get an object by URI."""
        raise NotImplementedError

    @abstractmethod
    async def get_me(self) -> str | None:
        """Get the current user's ID."""
        raise NotImplementedError

    @abstractmethod
    def get_ids_from_list(self, uris: list[str]) -> Coroutine[Any, Any, dict[str, str]]:
        """Get the IDs of objects by URIs."""
        # Checks the cache first, then calls get_id().
        raise NotImplementedError

    @abstractmethod
    def get_context(self, uri: str) -> Coroutine[Any, Any, list[str]]:
        """Get the context of an object by URI."""
        raise NotImplementedError

    @abstractmethod
    def get_status_by_id(
        self,
        status_id: str,
        semaphore: asyncio.Semaphore | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any] | Any]:
        """Get a status by ID."""
        raise NotImplementedError

    @abstractmethod
    def get_trending_statuses(
        self,
        limit: int = 40,
    ) -> list[dict[str, str]]:
        """Get trending statuses."""
        raise NotImplementedError

    @abstractmethod
    def get_following(
        self,
        user_id: str,
        limit: int = 40,
    ) -> list[dict[str, str]]:
        """Get the users the current user is following."""
        raise NotImplementedError

    @abstractmethod
    def get_followers(
        self,
        user_id: str,
        limit: int = 40,
    ) -> list[dict[str, str]]:
        """Get the users following the current user."""
        raise NotImplementedError

    @abstractmethod
    def get_follow_requests(
        self,
        limit: int = 40,
    ) -> list[dict[str, str]]:
        """Get the follow requests the current user has received."""
        raise NotImplementedError

    @abstractmethod
    def get_favourites(
        self,
        limit: int = 40,
    ) -> list[dict[str, str]]:
        """Get the statuses the current user has favourited."""
        raise NotImplementedError

    @abstractmethod
    async def get_bookmarks(
        self,
        limit: int = 40,
    ) -> list[dict[str, str]]:
        """Get the statuses the current user has bookmarked."""
        raise NotImplementedError

    @abstractmethod
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
        """Get the notifications for the current user."""
        raise NotImplementedError

    @abstractmethod
    async def get_remote_status_context(
        self,
        toot_id: str,
        home_server: str,
        home_token: str,
        _pgupdater: Any,
    ) -> list[str]:
        """Get the context of a status."""
        raise NotImplementedError

    @abstractmethod
    async def get_user_statuses(
        self,
        user_id: str,
        reply_since: datetime,
    ) -> list[dict[str, str]] | None:
        """Get the replies to a user."""
        raise NotImplementedError

    @abstractmethod
    async def get_home_timeline(
        self,
        limit: int = 40,
    ) -> list[dict[str, str]]:
        """Get the home timeline."""
        raise NotImplementedError

    @abstractmethod
    async def get_local_accounts(
        self,
        reply_interval_in_hours: int,
    ) -> list[dict[str, str]]:
        """Get local accounts with activity within interval."""
        raise NotImplementedError

class FederationInterface:
    """Interface for dependency injection of different federation APIs."""

    _equipped_api: API

    def __init__(self,
                domain: str,
                token: str | None = None,
                pgupdater: Any | None = None,
                ) -> None:
        """Initialize the API."""
        def _normalize_url(_url: str) -> str:
            """Normalize a URL."""
            if not _url.startswith("http"):
                _url = f"https://{_url}"
            if _url.endswith("/"):
                _url = _url[:-1]
            slashes_in_protocol_prefix = 2
            if _url.count("/") > slashes_in_protocol_prefix:
                _url = _url[:_url.find("/", 8)]
            return _url
        domain = _normalize_url(domain)
        temporary_client_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 +https://github.com/Teqed Meowstodon/1.0.0",  # noqa: E501
                },
            )
        temporary_client = HttpMethod(
                domain,
                temporary_client_session,
            )
        nodeinfo = asyncio.run(temporary_client.get("/nodeinfo/2.0"))
        if not nodeinfo:
            wellknown_nodeinfo = asyncio.run(temporary_client.get("/.well-known/nodeinfo"))
            if not wellknown_nodeinfo:
                raise NotImplementedError
            domain = _normalize_url(wellknown_nodeinfo["links"][0]["href"])
            temporary_client = HttpMethod(
                domain,
                temporary_client_session,
            )
            nodeinfo = asyncio.run(temporary_client.get("/nodeinfo/2.0"))
            if not nodeinfo:
                wellknown_hostmeta = asyncio.run(temporary_client.get("/.well-known/host-meta"))
                if wellknown_hostmeta and wellknown_hostmeta["server"]:
                    domain = _normalize_url(wellknown_hostmeta["server"])
                    temporary_client = HttpMethod(
                        domain,
                        temporary_client_session,
                    )
                    nodeinfo = asyncio.run(temporary_client.get("/nodeinfo/2.0"))
        software_name = nodeinfo["software"]["name"] if nodeinfo else None
        if software_name == "mastodon":
            from fedifetcher.api.mastodon import Mastodon
            equippable_api = Mastodon(domain, token, pgupdater)
        elif software_name == "misskey":
            raise NotImplementedError
        else:
            msg = f"Unknown software name: {software_name}"
            raise NotImplementedError(msg)
        self._equipped_api: API = equippable_api

    async def cleanup(self) -> None:
        """Clean up."""
        await self._equipped_api.cleanup()

    def get(self, uri: str) -> Coroutine[Any, Any, dict]:
        """Get an object by URI."""
        return self._equipped_api.get(uri)

    def get_ids_from_list(self, uris: list[str]) -> Coroutine[Any, Any, dict[str, str]]:
        """Get the IDs of objects by URIs."""
        return self._equipped_api.get_ids_from_list(uris)

    def get_context(self, uri: str) -> Coroutine[Any, Any, list[str]]:
        """Get the context of an object by URI."""
        return self._equipped_api.get_context(uri)

    def get_status_by_id(
        self,
        status_id: str,
        semaphore: asyncio.Semaphore | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any] | Any]:
        """Get a status by ID."""
        return self._equipped_api.get_status_by_id(status_id, semaphore)

    def get_trending_statuses(
        self,
        limit: int = 40,
    ) -> list[dict[str, str]]:
        """Get trending statuses."""
        return self._equipped_api.get_trending_statuses(limit)

    def get_following(
        self,
        user_id: str,
        limit: int = 40,
    ) -> list[dict[str, str]]:
        """Get the users the current user is following."""
        return self._equipped_api.get_following(user_id, limit)

    def get_followers(
        self,
        user_id: str,
        limit: int = 40,
    ) -> list[dict[str, str]]:
        """Get the users following the current user."""
        return self._equipped_api.get_followers(user_id, limit)

    def get_follow_requests(
        self,
        limit: int = 40,
    ) -> list[dict[str, str]]:
        """Get the follow requests the current user has received."""
        return self._equipped_api.get_follow_requests(limit)

    def get_favourites(
        self,
        limit: int = 40,
    ) -> list[dict[str, str]]:
        """Get the statuses the current user has favourited."""
        return self._equipped_api.get_favourites(limit)

    def get_bookmarks(
        self,
        limit: int = 40,
    ) -> Coroutine[Any, Any, list[dict[str, str]]]:
        """Get the statuses the current user has bookmarked."""
        return self._equipped_api.get_bookmarks(limit)

    def get_notifications(
        self,
        notification_id: str | None = None,
        max_id: str | None = None,
        since_id: str | None = None,
        min_id: str | None = None,
        limit: int = 40,
        types: list[str] | None = None,
        exclude_types: list[str] | None = None,
        account_id: str | None = None,
    ) -> Coroutine[Any, Any, list[dict[str, str]]]:
        """Get the notifications for the current user."""
        return self._equipped_api.get_notifications(
            notification_id,
            max_id,
            since_id,
            min_id,
            limit,
            types,
            exclude_types,
            account_id,
        )

    def get_status_context(
        self,
        toot_id: str,
        home_server: str,
        home_token: str,
        _pgupdater: Any,
    ) -> Coroutine[Any, Any, list[str]]:
        """Get the context of a status."""
        return self._equipped_api.get_remote_status_context(
            toot_id,
            home_server,
            home_token,
            _pgupdater,
        )

    def get_user_statuses(
        self,
        user_id: str,
        reply_since: datetime,
    ) -> Coroutine[Any, Any, list[dict[str, str]] | None]:
        """Get the replies to a user."""
        return self._equipped_api.get_user_statuses(user_id, reply_since)

    def get_home_timeline(
        self,
        limit: int = 40,
    ) -> Coroutine[Any, Any, list[dict[str, str]]]:
        """Get the home timeline."""
        return self._equipped_api.get_home_timeline(limit)

class FederationInterfaceManager:
    """Manage federation interfaces."""

    def __init__(self) -> None:
        """Initialize the manager."""
        self._interfaces: dict[str, FederationInterface] = {}

    def get_interface(self, domain: str) -> FederationInterface:
        """Get an interface."""
        if domain not in self._interfaces:
            self._interfaces[domain] = FederationInterface(domain)
        return self._interfaces[domain]

    async def cleanup(self) -> None:
        """Clean up."""
        for interface in self._interfaces.values():
            await interface.cleanup()
