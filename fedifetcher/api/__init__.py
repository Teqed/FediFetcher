"""__init__.py for api."""

from .api import API, FederationInterface
from .client import HttpMethod
from .firefish import api_firefish, api_firefish_types
from .lemmy import api_lemmy
from .mastodon import api_mastodon
from .postgresql import postgresql

__all__ = [
    "API",
    "HttpMethod",
    "FederationInterface",
    "api_firefish",
    "api_firefish_types",
    "api_lemmy",
    "api_mastodon",
    "postgresql",
]
