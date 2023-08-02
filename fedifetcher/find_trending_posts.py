"""Pull trending posts from a list of Mastodon servers, using tokens."""


import asyncio
import logging
import re
from collections.abc import Callable

from fedifetcher import parsers
from fedifetcher.api.mastodon import api_mastodon
from fedifetcher.api.postgresql import PostgreSQLUpdater

from .api.mastodon.api_mastodon_errors import MastodonError


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

    var_manip = VariableManipulators(
        domains_fetched, domains_to_fetch, remember_to_find_me)

    # with concurrent.futures.ThreadPoolExecutor(
    # ) as executor:
    #         executor.submit(
    #             external_tokens,
    #             trending_posts_dict,
    #             var_manip,
    #             aux_domain_fetcher,
    #             fetch_domain,
    #         for fetch_domain in external_feeds.copy()
    #     for future in concurrent.futures.as_completed(futures):
    #         if result:

    promises_container = []
    for fetch_domain in external_feeds.copy():
        promises_container.append(
            asyncio.ensure_future(fetch_and_return_missing(
                external_tokens,
                trending_posts_dict,
                var_manip,
                aux_domain_fetcher,
                fetch_domain,
            )),
        )
    await asyncio.gather(*promises_container)

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
        promises_container = {}
        promises = []
        for status_id in remember_to_find_me[fetch_domain]:
            if str(status_id) not in trending_posts_dict \
                    or "original" not in trending_posts_dict[str(status_id)]:
                promise = asyncio.ensure_future(
                        api_mastodon.Mastodon(fetch_domain,
                            external_tokens.get(fetch_domain)).get_status_by_id(
                            status_id),
                    )
                promises_container[status_id] = promise
                promises.append(promise)
        await asyncio.gather(*promises)
        for _status_id, future in promises_container.items():
            original_post = future.result()
            if original_post:
                add_post_to_dict(original_post, fetch_domain, trending_posts_dict)
            else:
                logging.warning(
                    f"Couldn't find {_status_id} from {fetch_domain}")

    logging.info(f"Fetching aux posts from {len(trending_posts_dict.keys())} domains")
    await aux_domain_fetcher.do_aux_fetches(trending_posts_dict, pgupdater)

    updated_trending_posts_dict = \
    await update_local_status_ids(
        trending_posts_dict, home_server, home_token, pgupdater)

    """Update the status stats with the trending posts."""
    if pgupdater:
        for post in updated_trending_posts_dict.values():
            local_status_id = post.get("local_status_id")
            if local_status_id:
                pgupdater.queue_status_update(
                    local_status_id,
                    int(post["reblogs_count"]),
                    int(post["favourites_count"]),
                )
        pgupdater.commit_status_updates()

    return list(api_mastodon.filter_language(
        updated_trending_posts_dict.values(), "en"))

async def fetch_and_return_missing(external_tokens : dict[str, str],
            trending_posts_dict : dict[str, dict[str, str]],
            var_manip,  # noqa: ANN001
            aux_domain_fetcher,  # noqa: ANN001
            fetch_domain : str,
            ) -> None:
    """Fetch posts from a domain."""
    await fetch_trending_from_domain(external_tokens,
        add_post_to_dict,
        var_manip.get_domains_to_fetch(),
        var_manip.get_domains_fetched(),
        var_manip.add_to_remembering,
        var_manip.get_remembering,
        aux_domain_fetcher, fetch_domain, trending_posts_dict)
    try:
        var_manip.add_to_fetched(fetch_domain)
        var_manip.remove_from_fetching(fetch_domain)
    except MastodonError:
        logging.error(
            f"Error occurred while fetching domain {fetch_domain}")

async def aux_domain_fetch(external_tokens : dict[str, str],  # noqa: PLR0913, C901
                    add_post_to_dict : Callable[[dict[str, str], str,
                                                dict[str, dict[str, str]]], bool],
                    domains_fetched : list[str],
                    post_urls : list[str],
                    parsed_urls : list[tuple[str | None, str | None]],
                    trending_post_dict : dict[str, dict[str, str]],
                    pgupdater : PostgreSQLUpdater,
                    ) -> bool:
    """Fetch posts from an aux domain."""
    msg = f"Finding aux trending posts from {parsed_urls[0][0]}"
    logging.info(f"\033[1;35m{msg}\033[0m")
    found_all = False
    if parsed_urls[0][0] is not None:
        cached_posts_dict = pgupdater.get_dict_from_cache(post_urls)
        for cached_post in cached_posts_dict.values():
            if cached_post and cached_post["url"] in post_urls:
                logging.debug(f"Found {cached_post['url']} in cache")
                post_urls.remove(cached_post["url"]) # Check originality?
        if not post_urls:
            return True
        trending = await api_mastodon.Mastodon(parsed_urls[0][0],
                external_tokens.get(parsed_urls[0][0])).get_trending_posts(120)
        domains_fetched.append(parsed_urls[0][0])
        if trending:
            for t_post in trending:
                if t_post["url"] in post_urls:
                    post_urls.remove(t_post["url"])
                add_post_to_dict(t_post, parsed_urls[0][0], trending_post_dict)
    for post_url in post_urls:
        parsed = parsers.post(post_url)
        if parsed and parsed[0] and parsed[0] == parsed_urls[0][0] and parsed[1]:
            remote = await api_mastodon.Mastodon(parsed[0],
                    external_tokens.get(parsed[0])).get_status_by_id(parsed[1])
            if remote and remote["url"] == post_url:
                add_post_to_dict(remote, parsed[0], trending_post_dict)
        else:
            logging.warning(f"Couldn't find {post_url} from {parsed_urls[0][0]}")
    if not post_urls:
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

    def queue_aux_fetch(self,
                            parsed_url: tuple[str | None, str | None],
                            post_url: str,
                            ) -> None:
        """Queue an aux fetch to be processed later."""
        if parsed_url[0] not in self.domains_fetched:
            logging.debug(f"Queueing {post_url} from {parsed_url[0]}")
            if parsed_url[0] not in self.aux_fetches:
                logging.debug(f"Adding {parsed_url[0]} to aux_fetches")
                self.aux_fetches[parsed_url[0]] = []
            if (parsed_url, post_url) not in self.aux_fetches[parsed_url[0]]:
                logging.debug(f"Adding {post_url} to aux_fetches[{parsed_url[0]}]")
                self.aux_fetches[parsed_url[0]].append((parsed_url, post_url))
                logging.debug(f"aux_fetches[{parsed_url[0]}] is now \
{self.aux_fetches[parsed_url[0]]}")

    async def do_aux_fetches(self,
                            trending_post_dict: dict[str, dict[str, str]],
                            pgupdater: PostgreSQLUpdater,
                            ) -> None:
        """Do all the queued aux fetches asynchronously."""

        async def fetching_domain(fetch_domain: str,
                                trending_post_dict: dict[str, dict[str, str]],
                                pgupdater: PostgreSQLUpdater,
                                ) -> None:
            """Fetch less popular posts from a domain."""
            msg = \
    f"Fetching {len(self.aux_fetches[fetch_domain])} popular posts from {fetch_domain}"
            logging.info(f"\033[1;34m{msg}\033[0m")
            list_of_posts = []
            list_of_parsed_urls = []
            _promises = []
            for parsed_url, post_url in self.aux_fetches[fetch_domain]:
                list_of_posts.append(post_url)
                list_of_parsed_urls.append(parsed_url)
                _promises.append(
                    asyncio.ensure_future(aux_domain_fetch(
                        self.external_tokens,
                        self.add_post_to_dict,
                        self.domains_fetched,
                        list_of_posts,
                        list_of_parsed_urls,
                        trending_post_dict,
                        pgupdater,
                    )),
                )
            await asyncio.gather(*_promises)
        promises = []
        for fetchable_domain in self.aux_fetches.copy():
            promises.append(
                asyncio.ensure_future(fetching_domain(
                    fetchable_domain,
                    trending_post_dict,
                    pgupdater,
                )),
            )
        await asyncio.gather(*promises)
        logging.debug(f"Clearing aux_fetches: {self.aux_fetches}")
        self.aux_fetches.clear()

async def fetch_trending_from_domain(  # noqa: C901, PLR0913
        external_tokens : dict[str, str],
        add_post_to_dict : Callable[[dict[str, str], str,
                                    dict[str, dict[str, str]]], bool],
        domains_to_fetch : list[str],
        domains_fetched : list[str],
        add_to_remembering : Callable[[str, str], None],
        get_remembering : Callable[[], dict[str, list[str]]],
        aux_domain_fetcher : AuxDomainFetch,
        fetch_domain : str,
        trending_posts_dict : dict[str, dict[str, str]],
        ) -> None:
    """Fetch trending posts from a domain."""
    msg = f"Fetching trending posts from {fetch_domain}"
    logging.info(f"\033[1;34m{msg}\033[0m")
    trending_posts = await api_mastodon.Mastodon(fetch_domain,
            external_tokens.get(fetch_domain)).get_trending_posts(200)

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
                remembering = get_remembering()
                if parsed_url[0] not in remembering or \
                            parsed_url[1] not in remembering[parsed_url[0]]:
                    logging.debug(f"Remembering {parsed_url[1]} from {parsed_url[0]}")
                    add_to_remembering(parsed_url[0], parsed_url[1])
                continue
            if parsed_url[0] not in domains_fetched:
                logging.debug(f"Queueing {parsed_url[1]} from {parsed_url[0]}")
                aux_domain_fetcher.queue_aux_fetch(parsed_url, post_url)
            elif not original:
                remote = await api_mastodon.Mastodon(parsed_url[0],
                    external_tokens.get(parsed_url[0])).get_status_by_id(parsed_url[1])
                if remote and remote["url"] == post_url:
                    original = add_post_to_dict(
                        remote, parsed_url[0], trending_posts_dict)
                if not original:
                    logging.warning(f"Couldn't find original for {post_url}")
    else:
        logging.warning(f"Couldn't find trending posts on {fetch_domain}")

async def update_local_status_ids(trending_posts_dict: dict[str, dict[str, str]],
                                home_server : str,
                                home_token : str,
                                pgupdater : PostgreSQLUpdater,
                                ) -> dict[str, dict[str, str]]:
    """Update the local_status_id in the trending_posts_dict."""
    list_of_trending_posts_urls = [
        trending_post["url"] for trending_post in trending_posts_dict.values()]
    home_status_dict = await api_mastodon.Mastodon(
        home_server, home_token, pgupdater).get_home_status_id_from_url_list(
        list_of_trending_posts_urls)
    for trending_post in trending_posts_dict.values():
        local_status_id = home_status_dict.get(trending_post["url"])
        if local_status_id:
            trending_post["local_status_id"] = local_status_id
    return trending_posts_dict
