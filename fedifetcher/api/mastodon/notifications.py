"""Mastodon API notifications endpoints."""
from collections.abc import Coroutine
from typing import Any

from fedifetcher.api.client import HttpMethod


class Notifications:
    """Class containing Mastodon API notifications endpoints."""

    def notifications(  # noqa: PLR0913
        self,
        client: HttpMethod,
        notification_id: str | None = None,
        max_id: str | None = None,
        since_id: str | None = None,
        min_id: str | None = None,
        limit: int | None = None,
        types: list[str] | None = None,
        exclude_types: list[str] | None = None,
        account_id: str | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any] | None]:
        """Notifications concerning the user.

        Reference: https://docs.joinmastodon.org/methods/notifications/#get
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
        if types:
            params["types"] = types
        if exclude_types:
            params["exclude_types"] = exclude_types
        if account_id:
            params["account_id"] = account_id
        if notification_id:
            return client.get(f"/api/v1/notifications/{notification_id}")
        return client.get("/api/v1/notifications", params=params)
