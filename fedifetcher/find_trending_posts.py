"""Pull trending posts from a list of Mastodon servers, using tokens."""


import asyncio
import concurrent.futures
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

class VariableManipulators:
    """Takes care of domains_fetched, domains_to_fetch, and remember_to_find_me."""

    def __init__(self, domains_fetched : list[str],
                domains_to_fetch : list[str],
                remember_to_find_me : dict[str, list[str]],
                ) -> None:
        """Initialize the VariableManipulators."""
        self.domains_fetched = domains_fetched
        self.domains_to_fetch = domains_to_fetch
        self.remember_to_find_me = remember_to_find_me

    def add_to_remembering(self, fetch_domain : str,
                            status_id : str) -> None:
        """Add a status URL to the remember_to_find_me dict."""
        if fetch_domain not in self.remember_to_find_me:
            self.remember_to_find_me[fetch_domain] = []
        if status_id not in self.remember_to_find_me[fetch_domain]:
            self.remember_to_find_me[fetch_domain].append(status_id)

    def remove_from_remembering(self, fetch_domain : str,
                                status_id : str) -> None:
        """Remove a status ID from the remember_to_find_me dict."""
        if fetch_domain in self.remember_to_find_me:
            if status_id in self.remember_to_find_me[fetch_domain]:
                self.remember_to_find_me[fetch_domain].remove(status_id)
            if not self.remember_to_find_me[fetch_domain]:
                self.remember_to_find_me.pop(fetch_domain)

    def get_remembering(self) -> dict[str, list[str]]:
        """Return the remember_to_find_me dict."""
        return self.remember_to_find_me

    def add_to_fetched(self, fetch_domain : str) -> None:
        """Add a domain to the domains_fetched list."""
        if fetch_domain not in self.domains_fetched:
            self.domains_fetched.append(fetch_domain)

    def remove_from_fetched(self, fetch_domain : str) -> None:
        """Remove a domain from the domains_fetched list."""
        if fetch_domain in self.domains_fetched:
            self.domains_fetched.remove(fetch_domain)

    def get_domains_fetched(self) -> list[str]:
        """Return the domains_fetched list."""
        return self.domains_fetched

    def add_to_fetching(self, fetch_domain : str) -> None:
        """Add a domain to the domains_to_fetch list."""
        if fetch_domain not in self.domains_to_fetch:
            self.domains_to_fetch.append(fetch_domain)

    def remove_from_fetching(self, fetch_domain : str) -> None:
        """Remove a domain from the domains_to_fetch list."""
        if fetch_domain in self.domains_to_fetch:
            self.domains_to_fetch.remove(fetch_domain)

    def get_domains_to_fetch(self) -> list[str]:
        """Return the domains_to_fetch list."""
        return self.domains_to_fetch

async def find_trending_posts(
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

    var_manip = VariableManipulators(
        domains_fetched, domains_to_fetch, remember_to_find_me)

    with concurrent.futures.ThreadPoolExecutor(
            thread_name_prefix="fetcher",
    ) as executor:
        futures = [
            executor.submit(
                fetch_and_return_missing,
                external_tokens,
                trending_posts_dict,
                var_manip,
                aux_domain_fetcher,
                fetch_domain,
            )
            for fetch_domain in external_feeds.copy()
        ]
        concurrent.futures.wait(futures)
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                logging.debug(f"Remembering {result}")

    remember_to_find_me = var_manip.get_remembering()
    domains_fetched = var_manip.get_domains_fetched()
    domains_to_fetch = var_manip.get_domains_to_fetch()

    for fetch_domain in remember_to_find_me.copy():
        if remember_to_find_me[fetch_domain] is False:
            remember_to_find_me.pop(fetch_domain)

    for fetch_domain in remember_to_find_me:
        msg = f"Fetching {len(remember_to_find_me[fetch_domain])} \
less popular posts from {fetch_domain}"
        logging.info(
            f"\033[1;34m{msg}\033[0m")
        for status_id in remember_to_find_me[fetch_domain]:
            logging.debug(f"Fetching {status_id} from {fetch_domain}")
            if str(status_id) not in trending_posts_dict \
                    or "original" not in trending_posts_dict[str(status_id)]:
                original_post = await api_mastodon.get_status_by_id(
                    fetch_domain, status_id, external_tokens)
                if original_post:
                    add_post_to_dict(original_post, fetch_domain, trending_posts_dict)
                else:
                    logging.warning(
                        f"Couldn't find {status_id} from {fetch_domain}")

    logging.info("Fetching aux posts")
    await aux_domain_fetcher.do_aux_fetches(trending_posts_dict)

    updated_trending_posts_dict = await \
    update_local_status_ids(
        trending_posts_dict, home_server, home_token, pgupdater)

    """Update the status stats with the trending posts."""
    if pgupdater:
        for post in updated_trending_posts_dict.values():
            local_status_id = post.get("local_status_id")
            if local_status_id:
                pgupdater.queue_status_update(
                    int(local_status_id),
                    int(post["reblogs_count"]),
                    int(post["favourites_count"]),
                )
        pgupdater.commit_status_updates()

    return list(api_mastodon.filter_language(
        updated_trending_posts_dict.values(), "en"))

def fetch_and_return_missing(external_tokens : dict[str, str],
            trending_posts_dict : dict[str, dict[str, str]],
            var_manip,  # noqa: ANN001
            aux_domain_fetcher,  # noqa: ANN001
            fetch_domain : str,
            ) -> None:
    """Fetch posts from a domain."""
    remembering = asyncio.run(fetch_trending_from_domain(external_tokens,
        add_post_to_dict, var_manip.get_domains_to_fetch(),
        var_manip.get_domains_fetched(), var_manip.get_remembering(),
        aux_domain_fetcher, fetch_domain, trending_posts_dict))
    try:
        var_manip.add_to_remembering(fetch_domain, remembering)
        var_manip.add_to_fetched(fetch_domain)
        var_manip.remove_from_fetching(fetch_domain)
    except MastodonError:
        logging.error(
            f"Error occurred while fetching domain {fetch_domain}")

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
        parsed = parsers.post(post_url)
        if parsed and parsed[0] and parsed[0] == parsed_urls[0][0] and parsed[1]:
            remote = await api_mastodon.get_status_by_id(
                    parsed[0], parsed[1], external_tokens)
            if remote and remote["url"] == post_url:
                add_post_to_dict(remote, parsed[0], trending_post_dict)
        else:
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

        def fetching_domain(fetch_domain: str,
                                trending_post_dict: dict[str, dict[str, str]]) -> None:
            """Fetch less popular posts from a domain."""
            msg = \
    f"Fetching {len(self.aux_fetches[fetch_domain])} popular posts from {fetch_domain}"
            logging.info(f"\033[1;34m{msg}\033[0m")
            list_of_posts = []
            list_of_parsed_urls = []
            for parsed_url, post_url in self.aux_fetches[fetch_domain]:
                list_of_posts.append(post_url)
                list_of_parsed_urls.append(parsed_url)
            asyncio.run(aux_domain_fetch(self.external_tokens, self.add_post_to_dict,
                self.domains_fetched, list_of_posts,
                    list_of_parsed_urls, trending_post_dict))
        # Create a thread pool executor
        with concurrent.futures.ThreadPoolExecutor(
                thread_name_prefix="aux_fetcher",
        ) as executor:
            # Create a list of futures
            futures = [
                executor.submit(
                    fetching_domain,
                    fetchable_domain,
                    trending_post_dict,
                )
                for fetchable_domain in self.aux_fetches.copy()
            ]
            # Wait for all the futures to complete
            concurrent.futures.wait(futures)
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    logging.debug(f"Remembering {result}")


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
            fetch_domain, external_tokens.get(fetch_domain), 120)
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
    list_of_trending_posts_urls = [
        trending_post["url"] for trending_post in trending_posts_dict.values()]
    home_status_dict = await api_mastodon.get_home_status_id_from_url_list(
        home_server, home_token, list_of_trending_posts_urls, pgupdater)
    for trending_post in trending_posts_dict.values():
        local_status_id = home_status_dict.get(trending_post["url"])
        if local_status_id:
            trending_post["local_status_id"] = local_status_id
    return trending_posts_dict
