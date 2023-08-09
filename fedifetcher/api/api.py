"""Interface for dependency injection of different APIs."""

from abc import ABCMeta, abstractmethod
from collections.abc import Coroutine
from typing import Any


class API(metaclass=ABCMeta):
    """Interface for dependency injection of different APIs."""

    @abstractmethod
    def get(self, uri: str) -> Coroutine[Any, Any, dict | bool]:
        """Get an object by URI."""
        raise NotImplementedError

    @abstractmethod
    def get_id(self, uri: str) -> Coroutine[Any, Any, str | None]:
        """Get the ID of an object by URI."""
        # Checks the cache first, then calls get().
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


class FederationInterface:
    """Interface for dependency injection of different federation APIs."""

    _equipped_api: API

    def __init__(self, equippable_api: API) -> None:
        """Initialize the API."""
        self._equipped_api: API = equippable_api

    def get(self, uri: str) -> Coroutine[Any, Any, dict | bool]:
        """Get an object by URI."""
        return self._equipped_api.get(uri)

    def get_id(self, uri: str) -> Coroutine[Any, Any, str | None]:
        """Get the ID of an object by URI."""
        return self._equipped_api.get_id(uri)

    def get_ids_from_list(self, uris: list[str]) -> Coroutine[Any, Any, dict[str, str]]:
        """Get the IDs of objects by URIs."""
        return self._equipped_api.get_ids_from_list(uris)

    def get_context(self, uri: str) -> Coroutine[Any, Any, list[str]]:
        """Get the context of an object by URI."""
        return self._equipped_api.get_context(uri)
