"""Test the parsers."""
import pytest

from fedifetcher.parsers import post, user


class TestParsers:
    """Test the parsers."""

    class TestUser:
        """Test the user function."""

        def test_mastodon(self) -> None:
            """Test a Mastodon user URL."""
            url = "https://mastodon.social/@username"
            expected_result = ("mastodon.social", "username")
            result = user(url)
            assert result == expected_result

        def test_pleroma(self) -> None:
            """Test a Pleroma user URL."""
            url = "https://pleroma.site/users/username"
            expected_result = ("pleroma.site", "username")
            result = user(url)
            assert result == expected_result

        def test_lemmy(self) -> None:
            """Test a Lemmy user URL."""
            url = "https://lemmy.ml/u/username"
            expected_result = ("lemmy.ml", "username")
            result = user(url)
            assert result == expected_result

        def test_pixelfed(self) -> None:
            """Test a Pixelfed user URL."""
            url = "https://pixelfed.net/username"
            expected_result = ("pixelfed.net", "username")
            result = user(url)
            assert result == expected_result

        def test_invalid(self) -> None:
            """Test an invalid user URL."""
            url = "https://example.com"
            expected_result = None
            result = user(url)
            assert result == expected_result

    class TestPost:
        """Test the post function."""

        def test_mastodon(self) -> None:
            """Test a Mastodon post URL."""
            url = "https://mastodon.social/@username/123456"
            expected_result = ("mastodon.social", "123456")
            result = post(url)
            assert result == expected_result

        def test_mastodon_uri(self) -> None:
            """Test a Mastodon URI post URL."""
            url = "https://mastodon.social/users/username/statuses/123456"
            expected_result = ("mastodon.social", "123456")
            result = post(url)
            assert result == expected_result

        def test_pleroma(self) -> None:
            """Test a Pleroma post URL."""
            url = "https://pleroma.site/objects/123456"
            expected_result = ("pleroma.site", "123456")
            result = post(url)
            assert result == expected_result

        def test_pixelfed(self) -> None:
            """Test a Pixelfed post URL."""
            url = "https://pixelfed.net/p/username/123456"
            expected_result = ("pixelfed.net", "123456")
            result = post(url)
            assert result == expected_result

        def test_firefish(self) -> None:
            """Test a Firefish post URL."""
            url = "https://example.com/notes/123456"
            expected_result = ("example.com", "123456")
            result = post(url)
            assert result == expected_result

        def test_lemmy(self) -> None:
            """Test a Lemmy post URL."""
            url = "https://lemmy.ml/post/123456"
            expected_result = ("lemmy.ml", "123456")
            result = post(url)
            assert result == expected_result

        def test_invalid(self) -> None:
            """Test an invalid post URL."""
            url = "https://example.com"
            expected_result = (None, None)
            result = post(url)
            assert result == expected_result


if __name__ == "__main__":
    pytest.main()
