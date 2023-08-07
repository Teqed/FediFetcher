"""Test the Mastodon class."""
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest

from fedifetcher.api.mastodon.api_mastodon import Mastodon, MastodonClient
from fedifetcher.api.mastodon.api_mastodon_types import (
    Status,
)

pytest_plugins = ('pytest_asyncio',)  # noqa: Q000

class TestMastodonClient:
    """Test the MastodonClient class."""

    client: ClassVar[MastodonClient] = MastodonClient(
        token="token",  # noqa: S106
        api_base_url="example.com",
        client_session=MagicMock(),
    )

    class TestHandleResponseErrors:
        """Test the handle_response_errors method."""

        async def test_success(self) -> None:
            """Test a 200 response with a body (success)."""
            response = MagicMock(
                status=200,
                json=AsyncMock(return_value={"key": "value"}),
            )
            expected_result = {"key": "value"}
            result = await TestMastodonClient.client.handle_response_errors(response)
            assert result == expected_result

        async def test_success_no_body(self) -> None:
            """Test a 200 response without a body (success, {})."""
            response = MagicMock(
                status=200,
                json=AsyncMock(return_value={}),
            )
            expected_result = True
            result = await TestMastodonClient.client.handle_response_errors(response)
            assert result == expected_result

        async def test_failure(self) -> None:
            """Test a 400 response (failure)."""
            response = MagicMock(
                status=400,
                json=AsyncMock(return_value={"error": "error"}),
            )
            expected_result = False
            result = await TestMastodonClient.client.handle_response_errors(response)
            assert result == expected_result

        async def test_failure_no_body(self) -> None:
            """Test a 401 response."""
            response = MagicMock(
                status=401,
                json=AsyncMock(return_value={"error": "error"}),
            )
            expected_result = False
            result = await TestMastodonClient.client.handle_response_errors(response)
            assert result == expected_result

        async def test_failure_no_json(self) -> None:
            """Test a 403 response."""
            response = MagicMock(
                status=403,
                json=AsyncMock(return_value={"error": "error"}),
            )
            expected_result = False
            result = await TestMastodonClient.client.handle_response_errors(response)
            assert result == expected_result

        async def test_failure_no_error(self) -> None:
            """Test a 418 response."""
            response = MagicMock(
                status=418,
                json=AsyncMock(return_value={"error": "error"}),
            )
            expected_result = False
            result = await TestMastodonClient.client.handle_response_errors(response)
            assert result == expected_result

        async def test_failure_no_status(self) -> None:
            """Test a 429 response."""
            response = MagicMock(
                status=429,
                json=AsyncMock(return_value={"error": "error"}),
            )
            expected_result = False
            result = await TestMastodonClient.client.handle_response_errors(response)
            assert result == expected_result

        async def test_failure_no_response(self) -> None:
            """Test a 500 response."""
            response = MagicMock(
                status=500,
                json=AsyncMock(return_value={"error": "error"}),
            )
            expected_result = False
            result = await TestMastodonClient.client.handle_response_errors(response)
            assert result == expected_result

        async def test_unknown_response(self) -> None:
            """Test an unknown response (failure)."""
            response = MagicMock(
                json=AsyncMock(return_value={"error": "error"}),
            )
            expected_result = False
            result = await TestMastodonClient.client.handle_response_errors(response)
            assert result == expected_result


class TestMastodon:
    """Test the Mastodon class."""

    pgupdater: ClassVar = MagicMock()
    mastodon: ClassVar[Mastodon] = Mastodon("example.com", "token", pgupdater)

    # userlite_mock: ClassVar[UserLite] = UserLite(
    #             id="123456",
    #             username="username",
    #             name="name",
    #             avatarUrl="https://example.com/avatar.png",
    #             avatarBlurhash="blurhash",
    #             avatarColor="#000000",
    #             host="example.com",
    #         )
    note_mock: ClassVar[Status] = Status(
            id="123456",
            text="text",
            createdAt="2021-01-01T00:00:00.000Z",
            cw="text",
            userId="123456",
            # user=userlite_mock,
            replyId="123456",
            renoteId="123456",
            renoteCount=1,
            repliesCount=1,
            uri="https://example.com/@username/123456",
        )

    async def test_init(self) -> None:
        """Test the __init__ method."""
        # Test a successful __init__
        assert isinstance(self.mastodon, Mastodon)

    async def test_add_context_url_success(self)-> None:
        """Test the add_context_url method."""
        # Test a successful add_context_url
        self.mastodon.client.ap_show = AsyncMock(return_value=("Note", self.note_mock))
        result = await self.mastodon.get("url")
        assert result == self.note_mock

    async def test_add_context_url_failed(self)-> None:
        """Test the add_context_url method."""
        self.mastodon.client.ap_show = AsyncMock(return_value=False)
        result = await self.mastodon.get("url")
        assert result is False

    async def test_get_home_status_id_from_url(self) -> None:
        """Test the get_home_status_id_from_url method."""
        self.mastodon.client.pgupdater = MagicMock()
        self.mastodon.client.pgupdater.get_from_cache = MagicMock(
            return_value={"id": "123456"})
        self.mastodon.get = AsyncMock(return_value={"id": "123456"})
        expected_result = "123456"
        result = await self.mastodon.get_id("url")
        assert result == expected_result

    async def test_get_home_status_id_from_url_failed(self) -> None:
        """Test the get_home_status_id_from_url method."""
        self.mastodon.client.pgupdater = MagicMock()
        self.mastodon.client.pgupdater.get_from_cache = MagicMock(return_value=None)
        self.mastodon.get = AsyncMock(return_value=False)
        expected_result = None
        result = await self.mastodon.get_id("url")
        assert result == expected_result

    async def test_get_home_status_id_from_url_list(self) -> None:
        """Test the get_home_status_id_from_url_list method."""
        self.mastodon.client.pgupdater = MagicMock()
        self.mastodon.client.pgupdater.get_dict_from_cache = MagicMock(
            return_value={"url": {"id": "123456"}})
        self.mastodon.get = AsyncMock(return_value={"id": "123456"})
        expected_result = {"url": "123456"}
        result = await self.mastodon.get_ids_from_list(["url"])
        assert result == expected_result

    async def test_get_toot_context(self) -> None:
        """Test the get_toot_context method."""
        self.mastodon.client.pgupdater = MagicMock()
        self.mastodon.client.pgupdater.queue_status_update = MagicMock()
        self.mastodon.client.pgupdater.commit_status_updates = MagicMock()
        self.mastodon.get_ids_from_list = AsyncMock(
            return_value={"url": "123456"})
        mastodon = MagicMock()
        mastodon.status_context = AsyncMock(
            return_value={
                "ancestors": [{"url": "https://example.com"}], "descendants": []})
        expected_result = ["https://example.com"]
        result = await self.mastodon.get_context(
            "123456", mastodon,
        )
        assert result == expected_result


if __name__ == "__main__":
    pytest.main()
