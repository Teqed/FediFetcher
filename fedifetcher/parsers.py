import helpers as helper
import re

def user():
    def url(url):
        match = mastodon_profile(url)
        if match:
            return match

        match = pleroma_profile(url)
        if match:
            return match

        match = lemmy_profile(url)
        if match:
            return match

# Pixelfed profile paths do not use a subdirectory, so we need to match for them last.
        match = pixelfed_profile(url)
        if match:
            return match

        helper.log(f"Error parsing Profile URL {url}")

        return None

    def mastodon_profile(url):
        """parse a Mastodon Profile URL and return the server and username"""
        match = re.match(
            r"https://(?P<server>[^/]+)/@(?P<username>[^/]+)", url)
        if match:
            return (match.group("server"), match.group("username"))
        return None

    def pleroma_profile(url):
        """parse a Pleroma Profile URL and return the server and username"""
        match = re.match(r"https://(?P<server>[^/]+)/users/(?P<username>[^/]+)", url)
        if match:
            return (match.group("server"), match.group("username"))
        return None

    def pixelfed_profile(url):
        """parse a Pixelfed Profile URL and return the server and username"""
        match = re.match(r"https://(?P<server>[^/]+)/(?P<username>[^/]+)", url)
        if match:
            return (match.group("server"), match.group("username"))
        return None

    def lemmy_profile(url):
        """parse a Lemmy Profile URL and return the server and username"""
        match = re.match(r"https://(?P<server>[^/]+)/(?:u|c)/(?P<username>[^/]+)", url)
        if match:
            return (match.group("server"), match.group("username"))
        return None


def post():
    def parse_url(url, parsed_urls):
        if url not in parsed_urls:
            match = parse_mastodon_url(url)
            if match:
                parsed_urls[url] = match

        if url not in parsed_urls:
            match = parse_pleroma_url(url)
            if match:
                parsed_urls[url] = match

        if url not in parsed_urls:
            match = parse_lemmy_url(url)
            if match:
                parsed_urls[url] = match

        if url not in parsed_urls:
            match = parse_pixelfed_url(url)
            if match:
                parsed_urls[url] = match

        if url not in parsed_urls:
            helper.log(f"Error parsing toot URL {url}")
            parsed_urls[url] = None
        return parsed_urls[url]

    def parse_mastodon_url(url):
        """parse a Mastodon URL and return the server and ID"""
        match = re.match(
            r"https://(?P<server>[^/]+)/@(?P<username>[^/]+)/(?P<toot_id>[^/]+)", url
        )
        if match:
            return (match.group("server"), match.group("toot_id"))
        return None

    def parse_pixelfed_url(url):
        """parse a Pixelfed URL and return the server and ID"""
        match = re.match(
            r"https://(?P<server>[^/]+)/p/(?P<username>[^/]+)/(?P<toot_id>[^/]+)", url
        )
        if match:
            return (match.group("server"), match.group("toot_id"))
        return None

    def parse_pleroma_url(url):
        """parse a Pleroma URL and return the server and ID"""
        match = re.match(r"https://(?P<server>[^/]+)/objects/(?P<toot_id>[^/]+)", url)
        if match:
            server = match.group("server")
            url = get_redirect_url(url)
            if url is None:
                return None

            match = re.match(r"/notice/(?P<toot_id>[^/]+)", url)
            if match:
                return (server, match.group("toot_id"))
            return None
        return None

    def parse_lemmy_url(url):
        """parse a Lemmy URL and return the server, and ID"""
        match = re.match(
            r"https://(?P<server>[^/]+)/(?:comment|post)/(?P<toot_id>[^/]+)", url
        )
        if match:
            return (match.group("server"), match.group("toot_id"))
        return None
