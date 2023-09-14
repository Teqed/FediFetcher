"""Mastodon API relationships endpoints."""
from collections.abc import Coroutine
from typing import Any

from fedifetcher.api.client import HttpMethod


class Relationships:
    """Class containing Mastodon API relationships endpoints."""

    def follow_requests(
        self,
        client: HttpMethod,
        max_id: str | None = None,
        since_id: str | None = None,
        limit: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any] | None]:
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
        return client.get("/api/v1/follow_requests", params=params)
