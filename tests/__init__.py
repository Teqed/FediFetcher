"""__init__.py for tests."""

from . import test_api_firefish, test_client, test_parsers
from .api.mastodon import test_api_mastodon

__all__ = [
    "test_api_firefish",
    "test_api_mastodon",
    "test_client",
    "test_parsers",
]
