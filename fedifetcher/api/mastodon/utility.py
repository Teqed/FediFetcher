"""Mastodon API utility endpoints."""
from collections.abc import Coroutine
from typing import Any

from fedifetcher.api.client import HttpMethod


class Utility:
    """Class containing Mastodon API utility endpoints."""

    def fetch_next(
        self,
        client: HttpMethod,
        previous_page: dict[str, Any],
    ) -> Coroutine[Any, Any, dict[str, Any] | None]:
        """Fetch the next page of results.

        Reference: https://docs.joinmastodon.org/api/guidelines/#pagination
        """
        return client.get(previous_page["_pagination_next"])
