"""Pull trending posts from a list of Mastodon servers, using tokens."""


import asyncio
import functools
import logging
import re
from collections.abc import Callable

import aiohttp
from mastodon.errors import MastodonError

from fedifetcher import api_mastodon, parsers
from fedifetcher.postgresql import PostgreSQLUpdater


def increment_count(post_url : str, incrementing_post : dict[str, str],
                    trending_posts_dict: dict[str, dict[str, str]]) -> None:
    """Increment the reblogs_count and favourites_count of a post."""
    if incrementing_post["reblogs_count"] \
            > trending_posts_dict[post_url]["reblogs_count"]:
        trending_posts_dict[post_url]["reblogs_count"] \
            = incrementing_post["reblogs_count"]
    trending_posts_dict[post_url]["favourites_count"] \
        += incrementing_post["favourites_count"]

def add_post_to_dict(trending_post : dict[str, str],
                    fetched_from_domain : str,
                    trending_posts_dict: dict[str, dict[str, str]],
                    ) -> bool:
    """Add a trending post to the trending_posts_dict, if it's not already there.

    Args:
    ----
    trending_post (dict[str, str]): The trending post to add.
    fetched_from_domain (str): The domain the trending post was fetched from.
    trending_posts_dict (dict[str, dict[str, str]]): The dict to add the post to.

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
            increment_count(t_post_url, trending_post, trending_posts_dict)
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


async def find_trending_posts(  # noqa: C901
        home_server: str,
        home_token: str,
        external_feeds: list[str],
        external_tokens: dict[str, str],
        pgupdater: PostgreSQLUpdater,
        ) -> list[dict[str, str]]:
    """Pull trending posts from a list of Mastodon servers, using tokens."""
    msg = f"Finding trending posts from {len(external_feeds)} domains:"
    logging.info(f"\033[1;34m{msg}\033[0m")

    # For each key in external_tokens, query its mastodon API for trending posts.
    # Later, we're going to compare these results to each other.
    trending_posts_dict: dict[str, dict[str, str]] = {}

    domains_to_fetch = external_feeds.copy()
    for domain in domains_to_fetch:
        logging.info(domain)
    domains_fetched = []
    remember_to_find_me : dict[str, list[str]] = {}
    aux_domain_fetcher = AuxDomainFetch(external_tokens, add_post_to_dict,
                                        domains_fetched)
    def on_task_done(task : asyncio.Task,  # noqa: PLR0913
                    domain : str,
                    externals : dict[str, asyncio.Task],
                    remember_to_find_me : dict[str, list[str]],
                    domains_fetched : list[str],
                    domains_to_fetch : list[str],
                    ) -> None:
        try:
            result = task.result()
            remember_to_find_me.update(result)
            domains_fetched.append(domain)
            domains_to_fetch.remove(domain)
        except MastodonError:
            logging.error(
                f"Error occurred while fetching domain {domain}")
        finally:
            del externals[domain]

    externals = {}
    for fetch_domain in external_feeds.copy():
        task = asyncio.create_task(fetch_trending_from_domain(external_tokens,
            add_post_to_dict, domains_to_fetch, domains_fetched, remember_to_find_me,
            aux_domain_fetcher, fetch_domain, trending_posts_dict))
        task.add_done_callback(functools.partial(on_task_done, domain=fetch_domain,
                externals=externals, remember_to_find_me=remember_to_find_me,
                domains_fetched=domains_fetched, domains_to_fetch=domains_to_fetch))
        externals[fetch_domain] = task
    await asyncio.gather(*externals.values())

    for fetch_domain in remember_to_find_me.copy():
        msg = f"Fetching {len(remember_to_find_me[fetch_domain])} \
less popular posts from {fetch_domain}"
        logging.info(
            f"\033[1;34m{msg}\033[0m")
        for status_id in remember_to_find_me[fetch_domain]:
            if status_id not in trending_posts_dict or \
                    "original" not in trending_posts_dict[status_id]:
                original_post = await api_mastodon.get_status_by_id(
                    fetch_domain, status_id, external_tokens)
                if original_post:
                    add_post_to_dict(original_post, fetch_domain, trending_posts_dict)
                else:
                    logging.warning(
                        f"Couldn't find {status_id} from {fetch_domain}")
        remember_to_find_me.pop(fetch_domain)

    logging.info("Fetching aux posts")
    await aux_domain_fetcher.do_aux_fetches(trending_posts_dict)

    updated_trending_posts_dict = await \
    update_local_status_ids(
        trending_posts_dict, home_server, home_token, pgupdater)

    """Update the status stats with the trending posts."""
    if pgupdater:
        for _url, post in trending_posts_dict.items():
            local_status_id = post["local_status_id"]
            if local_status_id:
                pgupdater.queue_status_update(
                    int(local_status_id),
                    int(post["reblogs_count"]),
                    int(post["favourites_count"]),
                )
        pgupdater.commit_status_updates()

    return list(api_mastodon.filter_language(
        updated_trending_posts_dict.values(), "en"))

async def aux_domain_fetch(external_tokens : dict[str, str],  # noqa: PLR0913
                    add_post_to_dict : Callable[[dict[str, str], str,
                                                dict[str, dict[str, str]]], bool],
                    domains_fetched : list[str],
                    post_urls : list[str],
                    parsed_urls : list[tuple[str | None, str | None]],
                    trending_post_dict : dict[str, dict[str, str]],
                    ) -> bool:
    """Fetch posts from an aux domain."""
    msg = f"Finding aux trending posts from {parsed_urls[0][0]}"
    logging.info(f"\033[1;35m{msg}\033[0m")
    found_all = False
    posts_to_find = post_urls.copy()
    if parsed_urls[0][0] is not None:
        trending = await api_mastodon.get_trending_posts(
                        parsed_urls[0][0],
                        external_tokens.get(parsed_urls[0][0]), 40)
        domains_fetched.append(parsed_urls[0][0])
        if trending:
            for t_post in trending:
                if t_post["url"] in posts_to_find:
                    posts_to_find.remove(t_post["url"])
                add_post_to_dict(t_post, parsed_urls[0][0], trending_post_dict)
    for post_url in posts_to_find:
        logging.warning(f"Couldn't find {post_url} from {parsed_urls[0][0]}")
    if not posts_to_find:
        found_all = True
    return found_all

# Let's define a class to store aux domain fetches. It'll have a function to queue
# them up, and then we'll do them all at once later.
class AuxDomainFetch:
    """A class for storing aux domain fetches."""

    def __init__(self, external_tokens: dict[str, str],
                add_post_to_dict,  # noqa: ANN001
                domains_fetched: list[str],
                ) -> None:
        """Initialize the AuxDomainFetch."""
        self.external_tokens = external_tokens
        self.add_post_to_dict = add_post_to_dict
        self.domains_fetched = domains_fetched
        self.aux_fetches = {}

    async def queue_aux_fetch(self,
                            parsed_url: tuple[str | None, str | None],
                            post_url: str,
                            ) -> None:
        """Queue an aux fetch to be processed later."""
        if parsed_url[0] not in self.domains_fetched:
            if parsed_url[0] not in self.aux_fetches:
                self.aux_fetches[parsed_url[0]] = []
            if (parsed_url, post_url) not in self.aux_fetches[parsed_url[0]]:
                self.aux_fetches[parsed_url[0]].append((parsed_url, post_url))

    async def do_aux_fetches(self,
                            trending_post_dict: dict[str, dict[str, str]],
                            ) -> None:
        """Do all the queued aux fetches asynchronously."""

        async def fetching_domain(fetch_domain: str,
                                trending_post_dict: dict[str, dict[str, str]]) -> None:
            msg = \
    f"Fetching {len(self.aux_fetches[fetch_domain])} popular posts from {fetch_domain}"
            logging.info(f"\033[1;34m{msg}\033[0m")
            list_of_posts = []
            list_of_parsed_urls = []
            for parsed_url, post_url in self.aux_fetches[fetch_domain]:
                list_of_posts.append(post_url)
                list_of_parsed_urls.append(parsed_url)
            await aux_domain_fetch(self.external_tokens, self.add_post_to_dict,
                self.domains_fetched, list_of_posts,
                    list_of_parsed_urls, trending_post_dict)

        tasks = [fetching_domain(fetchable_domain, trending_post_dict) \
                for fetchable_domain in self.aux_fetches.copy()]
        await asyncio.gather(*tasks)
        # Once all tasks are done, clear the aux_fetches
        self.aux_fetches.clear()

async def fetch_trending_from_domain(  # noqa: C901, PLR0913
        external_tokens : dict[str, str],
        add_post_to_dict : Callable[[dict[str, str], str,
                                    dict[str, dict[str, str]]], bool],
        domains_to_fetch : list[str],
        domains_fetched : list[str],
        remember_to_find_me : dict[str, list[str]],
        aux_domain_fetcher : AuxDomainFetch,
        fetch_domain : str,
        trending_posts_dict : dict[str, dict[str, str]],
        ) -> dict[str, list[str]]:
    """Fetch trending posts from a domain."""
    msg = f"Fetching trending posts from {fetch_domain}"
    logging.info(f"\033[1;34m{msg}\033[0m")
    trending_posts = await api_mastodon.get_trending_posts(
            fetch_domain, external_tokens.get(fetch_domain), 40)
    remember_to_find_me_updates : dict[str, list[str]] = {}

    if trending_posts:
        for post in trending_posts:
            post_url: str = post["url"]
            original = add_post_to_dict(post, fetch_domain, trending_posts_dict)
            if original:
                continue
            parsed_url = parsers.post(post_url)
            if not parsed_url or not parsed_url[0] or not parsed_url[1]:
                logging.warning(f"Error parsing post URL {post_url}")
                continue
            if parsed_url[0] in domains_to_fetch:
                if parsed_url[0] not in remember_to_find_me or \
                            parsed_url[1] not in remember_to_find_me[parsed_url[0]]:
                    if parsed_url[0] not in remember_to_find_me_updates:
                        remember_to_find_me_updates[parsed_url[0]] = []
                    remember_to_find_me_updates[parsed_url[0]].append(parsed_url[1])
                continue
            if parsed_url[0] not in domains_fetched:
                await aux_domain_fetcher.queue_aux_fetch(parsed_url, post_url)
            elif not original:
                remote = await api_mastodon.get_status_by_id(
                        parsed_url[0], parsed_url[1], external_tokens)
                if remote and remote["url"] == post_url:
                    original = add_post_to_dict(
                        remote, parsed_url[0], trending_posts_dict)
                if not original:
                    logging.warning(f"Couldn't find original for {post_url}")
    else:
        logging.warning(f"Couldn't find trending posts on {fetch_domain}")
    return remember_to_find_me_updates

async def update_local_status_ids(trending_posts_dict: dict[str, dict[str, str]],
                                home_server : str,
                                home_token : str,
                                pgupdater : PostgreSQLUpdater,
                                ) -> dict[str, dict[str, str]]:
    """Update the local_status_id in the trending_posts_dict."""
    async def fetch_status_id(url : str) -> tuple[str, str]:
        session = aiohttp.ClientSession()
        try:
            local_status_id = await api_mastodon.get_status_id_from_url(
                home_server, home_token, url, pgupdater, session)
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
