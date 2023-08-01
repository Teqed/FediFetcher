"""__init__.py for mastodon.

Submodules:
-----------
- Mastodon: Contains functions for interacting with the Mastodon API.
- api_mastodon_types: Contains type definitions for Mastodon API data
    structures
"""

from . import api_mastodon_types
from .api_mastodon import Mastodon

__all__ = ["Mastodon", "api_mastodon_types"]
