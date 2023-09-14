"""Mastodon API accounts endpoints."""
from collections.abc import Coroutine
from typing import Any

from fedifetcher.api.client import HttpMethod


class Accounts:
    """Class containing Mastodon API accounts endpoints."""

    def account_lookup(
        self,
        client: HttpMethod,
        acct: str,
    ) -> Coroutine[Any, Any, dict[str, Any] | None]:
        """Quickly lookup a username to see if it is available.

        Skips WebFinger resolution.

        Reference: https://docs.joinmastodon.org/methods/accounts/#lookup
        """
        return client.get("/api/v1/accounts/lookup", params={"acct": acct})

    async def account_statuses(
        self,
        client: HttpMethod,
        account_id: str,
        only_media: bool = False,
        pinned: bool = False,
        exclude_replies: bool = False,
        exclude_reblogs: bool = False,
        tagged: str | None = None,
        max_id: str | None = None,
        min_id: str | None = None,
        since_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Statuses posted to the given account.

        Reference: https://docs.joinmastodon.org/methods/accounts/#statuses
        """
        params = {}
        if only_media:
            params["only_media"] = only_media
        if pinned:
            params["pinned"] = pinned
        if exclude_replies:
            params["exclude_replies"] = exclude_replies
        if exclude_reblogs:
            params["exclude_reblogs"] = exclude_reblogs
        if tagged:
            params["tagged"] = tagged
        if max_id:
            params["max_id"] = max_id
        if min_id:
            params["min_id"] = min_id
        if since_id:
            params["since_id"] = since_id
        if limit:
            params["limit"] = limit

        status_json = await client.get(
            f"/api/v1/accounts/{account_id}/statuses",
            params=params,
        )
        if not status_json:
            return []
        status_list = status_json.get("list")
        if not status_list:
            return []
        return status_list

    def account_verify_credentials(
        self,
        client: HttpMethod,
    ) -> Coroutine[Any, Any, dict[str, Any] | None]:
        """Test to make sure that the user token works.

        Reference: https://docs.joinmastodon.org/methods/accounts/#verify_credentials
        """
        return client.get("/api/v1/accounts/verify_credentials")

    def account_following(
        self,
        client: HttpMethod,
        account_id: str,
        max_id: str | None = None,
        since_id: str | None = None,
        limit: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any] | None]:
        """Accounts which the given account is following.

        If network is not hidden by the account owner.

        Reference: https://docs.joinmastodon.org/methods/accounts/#following
        """
        params = {}
        if max_id:
            params["max_id"] = max_id
        if since_id:
            params["since_id"] = since_id
        if limit:
            params["limit"] = limit
        return client.get(
            f"/api/v1/accounts/{account_id}/following",
            params=params,
        )

    def account_followers(
        self,
        client: HttpMethod,
        account_id: str,
        max_id: str | None = None,
        since_id: str | None = None,
        limit: int | None = None,
    ) -> Coroutine[Any, Any, dict[str, Any] | None]:
        """Accounts which follow the given account.

        If network is not hidden by the account owner.

        Reference: https://docs.joinmastodon.org/methods/accounts/#followers
        """
        params = {}
        if max_id:
            params["max_id"] = max_id
        if since_id:
            params["since_id"] = since_id
        if limit:
            params["limit"] = limit
        return client.get(
            f"/api/v1/accounts/{account_id}/followers",
            params=params,
        )
