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
