"""Pull trending posts from a list of Mastodon servers, using tokens."""


import asyncio
import logging
import re

import aiohttp

from fedifetcher import api_mastodon, parsers
from fedifetcher.postgresql import PostgreSQLUpdater


async def find_trending_posts(  # noqa: C901, PLR0915, PLR0912, PLR0913
        home_server: str,
        home_token: str,
        external_feeds: list[str],
        external_tokens: dict[str, str],
        pgupdater: PostgreSQLUpdater | None,
        status_id_cache: dict[str, str],
        ) -> list[dict[str, str]]:
    """Pull trending posts from a list of Mastodon servers, using tokens."""
    msg = f"Finding trending posts from {len(external_feeds)} domains:"
    logging.info(f"\033[1;34m{msg}\033[0m")

    # For each key in external_tokens, query its mastodon API for trending posts.
    # Later, we're going to compare these results to each other.
    trending_posts_dict: dict[str, dict[str, str]] = {}

    def add_post_to_dict(trending_post : dict[str, str],
                        fetched_from_domain : str) -> bool:
        """Add a trending post to the trending_posts_dict, if it's not already there.

        Args:
        ----
        trending_post (dict[str, str]): The trending post to add.
        fetched_from_domain (str): The domain the trending post was fetched from.

        Returns:
        -------
        bool: True if the post was original, False otherwise.
        """
        t_post_url = trending_post["url"]
        original = re.search(
            r"https?://([a-zA-Z0-9_-]+\.)*(?:" + re.escape(fetched_from_domain) \
                + ")(?:/.*)?", t_post_url)
        if original:
            logging.info(
f"Reblogs: {trending_post['reblogs_count']} \
Favourites: {trending_post['favourites_count']} \
From: {t_post_url}")
            trending_posts_dict[t_post_url] = trending_post
            trending_posts_dict[t_post_url]["original"] = "Yes"
            return True
        if t_post_url in trending_posts_dict:
            if "original" not in trending_posts_dict[t_post_url]:
                logging.debug(
f"\033[3;33mReblogs: {trending_post['reblogs_count']} \
Favourites: {trending_post['favourites_count']} \
Copy: {t_post_url}\033[0m")
                increment_count(t_post_url, trending_post)
                return False
            logging.debug(
                f"Already seen {t_post_url} from origin")
            return True # We already have the original
        logging.debug(
f"\033[3;33mReblogs: {trending_post['reblogs_count']} \
Favourites: {trending_post['favourites_count']} \
Copy: {t_post_url}\033[0m")
        trending_posts_dict[t_post_url] = trending_post
        return False

    def increment_count(post_url : str, incrementing_post : dict[str, str]) -> None:
        """Increment the reblogs_count and favourites_count of a post."""
        if incrementing_post["reblogs_count"] \
                > trending_posts_dict[post_url]["reblogs_count"]:
            trending_posts_dict[post_url]["reblogs_count"] \
                = incrementing_post["reblogs_count"]
        trending_posts_dict[post_url]["favourites_count"] \
            += incrementing_post["favourites_count"]

    domains_to_fetch = external_feeds.copy()
    for domain in domains_to_fetch:
        logging.info(domain)
    domains_fetched = []
    remember_to_find_me : dict[str, list[str]] = {}
    for fetch_domain in external_feeds.copy():
        msg = f"Fetching trending posts from {fetch_domain}"
        logging.info(f"\033[1;34m{msg}\033[0m")
        trending_posts = api_mastodon.get_trending_posts(
            fetch_domain, external_tokens.get(fetch_domain), 2800)
        domains_fetched.append(fetch_domain)
        domains_to_fetch.remove(fetch_domain)

        if not trending_posts:
            logging.warning(f"Couldn't find trending posts on {fetch_domain}")
            continue
        for post in trending_posts:
            post_url: str = post["url"]
            original = add_post_to_dict(post, fetch_domain)
            if original:
                continue
            parsed_url = parsers.post(post_url)
            if not parsed_url or not parsed_url[0] or not parsed_url[1]:
                logging.warning(f"Error parsing post URL {post_url}")
                continue
            if parsed_url[0] in domains_to_fetch:
                if parsed_url[0] not in remember_to_find_me:
                    remember_to_find_me[parsed_url[0]] = []
                remember_to_find_me[parsed_url[0]].append(parsed_url[1])
                continue
            if parsed_url[0] not in domains_fetched:
                msg = f"Finding aux trending posts from {parsed_url[0]}"
                logging.info(f"\033[1;35m{msg}\033[0m")
                trending = api_mastodon.get_trending_posts(
                    parsed_url[0], external_tokens.get(parsed_url[0]), 720)
                domains_fetched.append(parsed_url[0])
                if trending:
                    for t_post in trending:
                        if add_post_to_dict(t_post, parsed_url[0]) \
                                and t_post["url"] == post_url:
                            original = True
            if not original:
                remote = api_mastodon.get_status_by_id(
                    parsed_url[0], parsed_url[1], external_tokens)
                if remote and remote["url"] == post_url:
                    original = add_post_to_dict(remote, parsed_url[0])
            if not original:
                logging.warning(f"Couldn't find original for {post_url}")
        if fetch_domain in remember_to_find_me:
            msg = f"Fetching {len(remember_to_find_me[fetch_domain])} \
less popular posts from {fetch_domain}"
            logging.info(
                f"\033[1;34m{msg}\033[0m")
            for status_id in remember_to_find_me[fetch_domain]:
                if status_id not in trending_posts_dict or \
                        "original" not in trending_posts_dict[status_id]:
                    original_post = api_mastodon.get_status_by_id(
                        fetch_domain, status_id, external_tokens)
                    if original_post:
                        add_post_to_dict(original_post, fetch_domain)
                    else:
                        logging.warning(
                            f"Couldn't find {status_id} from {fetch_domain}")
            remember_to_find_me.pop(fetch_domain)

    updated_trending_posts_dict = await \
    update_local_status_ids(
        trending_posts_dict, home_server, home_token, status_id_cache)

    """Update the status stats with the trending posts."""
    if pgupdater:
        for _url, post in trending_posts_dict.items():
            local_status_id = post["local_status_id"]
            if local_status_id:
                pgupdater.queue_update(
                    int(local_status_id),
                    int(post["reblogs_count"]),
                    int(post["favourites_count"]),
                )
        pgupdater.commit_updates()

    return list(updated_trending_posts_dict.values())

async def update_local_status_ids(trending_posts_dict: dict[str, dict[str, str]],
                                home_server : str,
                                home_token : str,
                                status_id_cache: dict[str, str],
                                ) -> dict[str, dict[str, str]]:
    """Update the local_status_id in the trending_posts_dict."""
    async def fetch_status_id(url : str) -> tuple[str, str]:
        session = aiohttp.ClientSession()
        try:
            local_status_id = await api_mastodon.get_status_id_from_url(
                home_server, home_token, url, status_id_cache, session)
            return url, local_status_id if local_status_id else ""
        finally:
            await session.close()

    tasks = [fetch_status_id(url) for url in trending_posts_dict]

    # Wait for all the tasks to complete
    results = await asyncio.gather(*tasks)

    # Update the local_status_id in the trending_posts_dict
    for url, local_status_id in results:
        trending_posts_dict[url]["local_status_id"] = \
            local_status_id if local_status_id else ""

    return trending_posts_dict
