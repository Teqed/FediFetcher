"""Mastodon API timeline endpoints."""
from collections.abc import Coroutine
from typing import Any

from fedifetcher.api.client import HttpMethod


class Timeline:
    """Class containing Mastodon API timeline endpoints."""

    def timelines_home(
        self,
        client: HttpMethod,
        max_id: str | None = None,
        since_id: str | None = None,
        min_id: str | None = None,
        limit: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any] | None]:
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
        return client.get("/api/v1/timelines/home", params=params)

    def timelines_public(
        self,
        client: HttpMethod,
        local: bool = False,
        remote: bool = False,
        only_media: bool = False,
        max_id: str | None = None,
        since_id: str | None = None,
        min_id: str | None = None,
        limit: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any] | None]:
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
        return client.get("/api/v1/timelines/public", params=params)
