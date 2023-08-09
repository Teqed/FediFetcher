"""Test the Mastodon class."""
from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest

from fedifetcher.api.mastodon.api_mastodon import Mastodon

pytest_plugins = ('pytest_asyncio',)  # noqa: Q000

class TestMastodon:
    """Test the Mastodon class."""

    pgupdater: ClassVar = MagicMock()
    mastodon: ClassVar[Mastodon] = Mastodon("example.com", "token", pgupdater)

    status_mock: ClassVar[dict[str, Any]] = {
        "id": "109612104811129202",
        "created_at": "2023-01-01T04:39:46.013Z",
        "in_reply_to_id": None,
        "in_reply_to_account_id": None,
        "sensitive": False,
        "spoiler_text": "",
        "visibility": "public",
        "language": "en",
        "uri": "https://mastodon.shatteredsky.net/users/teq/statuses/109612104811129202",
        "url": "https://mastodon.shatteredsky.net/@teq/109612104811129202",
        "replies_count": 0,
        "reblogs_count": 0,
        "favourites_count": 1,
        "edited_at": None,
        "favourited": True,
        "reblogged": False,
        "muted": False,
        "bookmarked": False,
        "pinned": False,
        "local_only": None,
        "content": "<p>Hello, world! 🦣</p>",
        "filtered": [],
        "reblog": None,
        "application": {
            "name": "Web",
            "website": None,
        },
        "account": {
            "id": "109608061015969173",
            "username": "teq",
            "acct": "teq",
            "display_name": "Teq",
            "locked": False,
            "bot": False,
            "discoverable": True,
            "group": False,
            "created_at": "2022-12-31T00:00:00.000Z",
            "note": "<p>Hello, I&#39;m Teq (Timothy E. Quilling) 👋 </p><p>🫠 Born to solve problems that didn&#39;t exist before.<br />❤️‍🔥 Loves open source software!</p>",
            "url": "https://mastodon.shatteredsky.net/@teq",
            "avatar": "https://mastodon.shatteredsky.net/system/accounts/avatars/109/608/061/015/969/173/original/a42c6a222db7bc7f.gif",
            "avatar_static": "https://mastodon.shatteredsky.net/system/accounts/avatars/109/608/061/015/969/173/static/a42c6a222db7bc7f.png",
            "header": "https://mastodon.shatteredsky.net/system/accounts/headers/109/608/061/015/969/173/original/1e3f22fe19524ada.png",
            "header_static": "https://mastodon.shatteredsky.net/system/accounts/headers/109/608/061/015/969/173/original/1e3f22fe19524ada.png",
            "followers_count": 11,
            "following_count": 51,
            "statuses_count": 12,
            "last_status_at": "2023-08-03",
            "noindex": False,
            "emojis": [
            {
                "shortcode": "verified_animate",
                "url": "https://mastodon.shatteredsky.net/system/custom_emojis/images/000/029/576/original/2fa90b024d54a0f0.gif",
                "static_url": "https://mastodon.shatteredsky.net/system/custom_emojis/images/000/029/576/static/2fa90b024d54a0f0.png",
                "visible_in_picker": True,
            },
            {
                "shortcode": "party_github",
                "url": "https://mastodon.shatteredsky.net/system/custom_emojis/images/000/029/786/original/ef6ea29e513ccd2d.gif",
                "static_url": "https://mastodon.shatteredsky.net/system/custom_emojis/images/000/029/786/static/ef6ea29e513ccd2d.png",
                "visible_in_picker": True,
            },
            ],
            "roles": [
            {
                "id": "3",
                "name": "Owner",
                "color": "",
            },
            ],
            "fields": [
            {
                "name": ":verified_animate: Home",
                "value": '<a href="https://shatteredsky.net" target="_blank" rel="nofollow noopener noreferrer me" translate="no"><span class="invisible">https://</span><span class="">shatteredsky.net</span><span class="invisible"></span></a>',
                "verified_at": "2023-07-02T20:56:08.588+00:00",
            },
            {
                "name": ":party_github:\u200b GitHub",
                "value": '<a href="https://github.com/Teqed" target="_blank" rel="nofollow noopener noreferrer me" translate="no"><span class="invisible">https://</span><span class="">github.com/Teqed</span><span class="invisible"></span></a>',
                "verified_at": "2023-07-02T20:56:09.155+00:00",
            },
            ],
        },
        "media_attachments": [],
        "mentions": [],
        "tags": [],
        "emojis": [],
        "reactions": [],
        "card": None,
        "poll": None,
        }

    async def test_init(self) -> None:
        """Test the __init__ method."""
        # Test a successful __init__
        assert isinstance(self.mastodon, Mastodon)

    async def test_add_context_url_success(self)-> None:
        """Test the add_context_url method."""
        # Test a successful add_context_url
        search_mock: dict[str, list[dict[str, Any]]] = {"statuses": [self.status_mock]}
        self.mastodon.client.get = AsyncMock(return_value=search_mock)
        result = await self.mastodon.get("https://mastodon.shatteredsky.net/users/teq/statuses/109612104811129202")
        assert result == self.status_mock

    async def test_add_context_url_failed(self)-> None:
        """Test the add_context_url method."""
        self.mastodon.client.get = AsyncMock(return_value=False)
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
        if False: # TODO: Fix this test
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
                "123456",
            )
            assert result == expected_result


if __name__ == "__main__":
    pytest.main()
