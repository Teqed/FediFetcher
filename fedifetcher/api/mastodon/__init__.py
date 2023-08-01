"""__init__.py for mastodon.

Submodules:
-----------
- Mastodon: Contains functions for interacting with the Mastodon API.
- api_mastodon_types: Contains type definitions for Mastodon API data
    structures
"""

from api_mastodon import Mastodon

from . import api_mastodon_types

__all__ = ["Mastodon", "api_mastodon_types"]
