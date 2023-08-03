"""Test the parsers."""
import unittest

from fedifetcher.parsers import post, user


class ParsersTest(unittest.TestCase):
    """Test the parsers."""

    def test_user(self) -> None:
        """Test the user function."""
        # Test a Mastodon user URL
        url = "https://mastodon.social/@username"
        expected_result = ("mastodon.social", "username")
        result = user(url)
        assert result == expected_result

        # Test a Pleroma user URL
        url = "https://pleroma.site/users/username"
        expected_result = ("pleroma.site", "username")
        result = user(url)
        assert result == expected_result

        # Test a Lemmy user URL
        url = "https://lemmy.ml/u/username"
        expected_result = ("lemmy.ml", "username")
        result = user(url)
        assert result == expected_result

        # Test a Pixelfed user URL
        url = "https://pixelfed.net/username"
        expected_result = ("pixelfed.net", "username")
        result = user(url)
        assert result == expected_result

        # Test an invalid user URL
        url = "https://example.com"
        expected_result = None
        result = user(url)
        assert result == expected_result

    def test_post(self) -> None:
        """Test the post function."""
        # Test a Mastodon post URL
        url = "https://mastodon.social/@username/123456"
        expected_result = ("mastodon.social", "123456")
        result = post(url)
        assert result == expected_result

        # Test a Mastodon URI post URL
        url = "https://mastodon.social/users/username/statuses/123456"
        expected_result = ("mastodon.social", "123456")
        result = post(url)
        assert result == expected_result

        # Test a Firefish post URL
        url = "https://example.com/notes/123456"
        expected_result = ("example.com", "123456")
        result = post(url)
        assert result == expected_result

        # Test a Pixelfed post URL
        url = "https://pixelfed.net/p/username/123456"
        expected_result = ("pixelfed.net", "123456")
        result = post(url)
        assert result == expected_result

        # Test a Pleroma post URL
        url = "https://pleroma.site/objects/123456"
        expected_result = ("pleroma.site", "123456")
        result = post(url)
        assert result == expected_result

        # Test a Lemmy post URL
        url = "https://lemmy.ml/comment/123456"
        expected_result = ("lemmy.ml", "123456")
        result = post(url)
        assert result == expected_result

        # Test an invalid post URL
        url = "https://example.com"
        expected_result = (None, None)
        result = post(url)
        assert result == expected_result


if __name__ == "__main__":
    unittest.main()
