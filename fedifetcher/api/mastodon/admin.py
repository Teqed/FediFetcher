"""Mastodon API admin endpoints."""
from collections.abc import Coroutine
from typing import Any

from fedifetcher.api.client import HttpMethod


class Admin:
    """Class containing Mastodon API admin endpoints."""

    def admin_accounts_v2(
        self,
        client: HttpMethod,
        origin: str | None = None,
        status: str | None = None,
        permissions: str | None = None,
        role_ids: list[str] | None = None,
        invited_by: str | None = None,
        username: str | None = None,
        display_name: str | None = None,
        by_domain: str | None = None,
        email: str | None = None,
        ip: str | None = None,
        max_id: str | None = None,
        since_id: str | None = None,
        min_id: str | None = None,
        limit: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any] | None]:
        """View all accounts.

        View all accounts, optionally matching certain criteria for filtering,
        up to 100 at a time. Pagination may be done with the HTTP Link header
        in the response. See Paginating through API responses for more information.

        Reference: https://docs.joinmastodon.org/methods/admin/accounts/#v2
        """
        params = {}
        if origin:
            params["origin"] = origin
        if status:
            params["status"] = status
        if permissions:
            params["permissions"] = permissions
        if role_ids:
            params["role_ids"] = role_ids
        if invited_by:
            params["invited_by"] = invited_by
        if username:
            params["username"] = username
        if display_name:
            params["display_name"] = display_name
        if by_domain:
            params["by_domain"] = by_domain
        if email:
            params["email"] = email
        if ip:
            params["ip"] = ip
        if max_id:
            params["max_id"] = max_id
        if since_id:
            params["since_id"] = since_id
        if min_id:
            params["min_id"] = min_id
        if limit:
            params["limit"] = limit
        return client.get("/api/v2/admin/accounts", params=params)
