"""Parsers for various Fediverse platforms.

Submodules:
-----------
- user: Provides parsing utilities for user URLs.
- post: Provides parsing utilities for post URLs.
"""
import logging
import re

from . import helpers


def user(unparsed_url: str) -> tuple[str, str] | None:
    """Parse a user URL and return the server and username.

    Args:
    ----
    unparsed_url (str): The URL of the profile.

    Returns:
    -------
    Tuple[str, str] | None: A tuple containing the server and username,
        or None if no match is found.
    """

    def parse_profile(url: str, pattern: str) -> tuple[str, str] | None:
        """Parse a profile URL using the provided regex pattern.

        Args:
        ----
        url (str): The URL of the profile.
        pattern (str): The regex pattern to match the URL.

        Returns:
        -------
        Tuple[str, str] | None: A tuple containing the server and username,
            or None if no match is found.
        """
        match = re.match(pattern, url)
        if match:
            return match.group("server"), match.group("username")
        return None

    fediverse_profile_regex: dict[str, str] = {
        "mastodon": r"https://(?P<server>[^/]+)/@(?P<username>[^/]+)",
        "pleroma": r"https://(?P<server>[^/]+)/users/(?P<username>[^/]+)",
        "lemmy": r"https://(?P<server>[^/]+)/(?:u|c)/(?P<username>[^/]+)",
        "pixelfed": r"https://(?P<server>[^/]+)/(?P<username>[^/]+)",  # Pixelfed last
    }

    for _each, pattern in fediverse_profile_regex.items():
        match = parse_profile(unparsed_url, pattern)
        if match:
            return match

    logging.exception(f"Error parsing user URL {unparsed_url}")
    return None

def post(
    unparsed_url: str,
    parsed_urls: dict[str, tuple[str | None, str | None]],
) -> tuple[str | None, str | None] | None:
    """Parse a post URL and return the server and toot ID.

    Args:
    ----
    unparsed_url (str): The URL of the post.
    parsed_urls (dict[str, tuple[str, str | None] | None]): \
        A dictionary to store parsed URLs and their results.

    Returns:
    -------
    tuple[str, str | None] | None: A tuple containing the server and toot ID,
        or None if no match is found.
    """
    def parse_post(url: str, pattern: str) -> tuple[str, str] | None:
        """Parse a post URL using the provided regex pattern.

        Args:
        ----
        url (str): The URL of the post.
        pattern (str): The regex pattern to match the URL.

        Returns:
        -------
        tuple[str, str] | None: A tuple containing the server and toot ID,
            or None if no match is found.
        """
        match = re.match(pattern, url)
        if match:
            return match.group("server"), match.group("toot_id")
        return None

    fediverse_post_regex: dict[str, str] = {
        "mastodon": r"https://(?P<server>[^/]+)/@(?P<username>[^/]+)/(?P<toot_id>[^/]+)",
        "pixelfed": r"https://(?P<server>[^/]+)/p/(?P<username>[^/]+)/(?P<toot_id>[^/]+)",
        "pleroma": r"https://(?P<server>[^/]+)/objects/(?P<toot_id>[^/]+)",
        "lemmy": r"https://(?P<server>[^/]+)/(?:comment|post)/(?P<toot_id>[^/]+)",
    }

    for _each, pattern in fediverse_post_regex.items():
        if unparsed_url not in parsed_urls:
            match = parse_post(unparsed_url, pattern)
            if match:
                parsed_urls[unparsed_url] = match

    if unparsed_url not in parsed_urls:
        logging.exception(f"Error parsing toot URL {unparsed_url}")
        parsed_urls[unparsed_url] = (None, None)

    return parsed_urls[unparsed_url]
