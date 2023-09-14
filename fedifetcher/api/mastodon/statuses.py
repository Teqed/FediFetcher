"""Mastodon API statuses endpoints."""
import asyncio
from collections.abc import Coroutine
from typing import Any

from fedifetcher.api.client import HttpMethod
from fedifetcher.api.mastodon.api_mastodon_types import Status


class Statuses:
    """Class containing Mastodon API statuses endpoints."""

    def status(
        self,
        client: HttpMethod,
        status_id: str,
        semaphore: asyncio.Semaphore | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any] | Status | None]:
        """Obtain information about a status.

        Reference: https://docs.joinmastodon.org/methods/statuses/#get
        """
        return client.get(f"/api/v1/statuses/{status_id}", semaphore=semaphore)

    def status_context(
        self,
        client: HttpMethod,
        status_id: str,
    ) -> Coroutine[Any, Any, dict[str, Any] | None]:
        """View statuses above and below this status in the thread.

        Reference: https://docs.joinmastodon.org/methods/statuses/#context
        """
        return client.get(f"/api/v1/statuses/{status_id}/context")
