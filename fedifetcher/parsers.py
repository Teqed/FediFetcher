import helpers as helper
import re
from typing import Optional, Tuple

def user():
    def parse_profile(url: str, pattern: str) -> Optional[Tuple[str, str]]:
        """Parse a profile URL using the provided regex pattern.

        Args:
            url (str): The URL of the profile.
            pattern (str): The regex pattern to match the URL.

        Returns:
            Optional[Tuple[str, str]]: A tuple containing the server and username,
            or None if no match is found.
        """
        match = re.match(pattern, url)
        if match:
            return match.group("server"), match.group("username")
        return None

    def url(url: str, profiles: dict) -> Optional[Tuple[str, str]]:
        """Parse a profile URL and return the server and username.

        Args:
            url (str): The URL of the profile.
            profiles (dict): The dictionary of profiles and their regex patterns.

        Returns:
            Optional[Tuple[str, str]]: A tuple containing the server and username,
            or None if no match is found.
        """
        for profile, pattern in profiles.items():
            match = parse_profile(url, pattern)
            if match:
                return match

        helper.log(f"Error parsing Profile URL {url}")
        return None

    profiles = {
        "mastodon": r"https://(?P<server>[^/]+)/@(?P<username>[^/]+)",
        "pleroma": r"https://(?P<server>[^/]+)/users/(?P<username>[^/]+)",
        "lemmy": r"https://(?P<server>[^/]+)/(?:u|c)/(?P<username>[^/]+)",
        "pixelfed": r"https://(?P<server>[^/]+)/(?P<username>[^/]+)",  # Pixelfed last
    }

    profile_functions = \
        {profile: lambda url: url(url, profiles) for profile in profiles}
    globals().update(profile_functions)


def post():
    def url(url, parsed_urls):
        for profile, pattern in profiles.items():
            if url not in parsed_urls:
                match = re.match(pattern, url)
                if match:
                    parsed_urls[url] = (match.group("server"), match.group("toot_id"))

        if url not in parsed_urls:
            helper.log(f"Error parsing toot URL {url}")
            parsed_urls[url] = None

        return parsed_urls[url]

    profiles = {
        "mastodon": r"https://(?P<server>[^/]+)/@(?P<username>[^/]+)/(?P<toot_id>[^/]+)",
        "pixelfed": r"https://(?P<server>[^/]+)/p/(?P<username>[^/]+)/(?P<toot_id>[^/]+)",
        "pleroma": r"https://(?P<server>[^/]+)/objects/(?P<toot_id>[^/]+)",
        "lemmy": r"https://(?P<server>[^/]+)/(?:comment|post)/(?P<toot_id>[^/]+)",
    }
