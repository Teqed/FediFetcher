"""Mastodon API favourites endpoints."""
from collections.abc import Coroutine
from typing import Any

from fedifetcher.api.client import HttpMethod


class Favourites:
    """Class containing Mastodon API favourites endpoints."""

    def favourites(
        self,
        client: HttpMethod,
        max_id: str | None = None,
        min_id: str | None = None,
        since_id: str | None = None,
        limit: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any] | None]:
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
        return client.get("/api/v1/favourites", params=params)

    def bookmarks(
        self,
        client: HttpMethod,
        max_id: str | None = None,
        since_id: str | None = None,
        min_id: str | None = None,
        limit: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any] | None]:
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
        return client.get("/api/v1/bookmarks", params=params)
