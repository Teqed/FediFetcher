"""Mastodon API trends endpoints."""
from collections.abc import Coroutine
from typing import Any

from fedifetcher.api.client import HttpMethod


class Trends:
    """Class containing Mastodon API trends endpoints."""

    def trending_statuses(
        self,
        client: HttpMethod,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any] | None]:
        """Get trending statuses.

        Reference: https://docs.joinmastodon.org/methods/trends/#statuses
        """
        params = {}
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
        return client.get("/api/v1/trends/statuses", params=params)
