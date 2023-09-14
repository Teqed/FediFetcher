"""Mastodon API search endpoints."""
from collections.abc import Coroutine
from typing import Any

from fedifetcher.api.client import HttpMethod


class Search:
    """Class containing Mastodon API search endpoints."""

    def search_v2(  # noqa: PLR0913
        self,
        client: HttpMethod,
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
    ) -> Coroutine[Any, Any, dict[str, Any] | None]:
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
        return client.get("/api/v2/search", params=params)
