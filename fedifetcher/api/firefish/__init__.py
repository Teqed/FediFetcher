"""__init__.py for firefish.

Submodules:
-----------
- api_firefish: Contains functions for interacting with the Firefish API.
- api_firefish_types: Contains type definitions for Firefish API data
    structures
"""

from api_firefish import Firefish
from api_firefish_types import Note, UserDetailedNotMe

__all__ = [
    "Firefish",
    "Note",
    "UserDetailedNotMe",
]
