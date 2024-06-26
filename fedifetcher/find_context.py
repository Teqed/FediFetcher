"""Add context toots to the server."""
import asyncio
import logging
from argparse import Namespace
from collections.abc import Iterable
from typing import TYPE_CHECKING

from fedifetcher import getter_wrappers, parsers
from fedifetcher.api.api import API, ApiError
from fedifetcher.api.postgresql import PostgreSQLUpdater

if TYPE_CHECKING:
    from fedifetcher.api.mastodon.types.api_mastodon_types import Status


async def add_post_with_context(
    post: dict[str, str],
    api: API,
    # home_server: str,
    # access_token: str,
    external_tokens: dict[str, str],
    # pgupdater: PostgreSQLUpdater,
    arguments: Namespace,
) -> bool:
    """Add the given post to the server.

    Args:
    ----
    post: The post to add.
    home_server: The server to add the post to.
    access_token: The access token to use to add the post.
    external_tokens: A dict of external tokens, keyed by server. If None, no \
        external tokens will be used.
    pgupdater: The PostgreSQL updater.

    Returns:
    -------
    bool: True if the post was added successfully, False otherwise.
    """
    try:
        await api.get(post["url"])
        if ("replies_count" in post or "in_reply_to_id" in post) and getattr(
            arguments,
            "backfill_with_context",
            0,
        ) > 0:
            parsed_urls: dict[str, tuple[str | None, str | None]] = {}
            parsed = parsers.post(post["url"], parsed_urls)
            if parsed is not None and parsed[0] is not None:
                if api.client.pgupdater is None or api.client.token is None:
                    msg = "No PostgreSQL updater, or no token"
                    raise ApiError(msg)
                known_context_urls = await getter_wrappers.get_all_known_context_urls(
                    api,
                    [post],
                    parsed_urls,
                    external_tokens,
                )
                (
                    await add_context_urls_wrapper(
                        api,
                        known_context_urls,
                    )
                )
            return True
    except ApiError:
        logging.debug(f"Failed to add {post['url']} to {api.client.api_base_url}")
    return False


async def add_context_urls_wrapper(
    api: API,
    context_urls: Iterable[str],
) -> None:
    """Add the given toot URLs to the server.

    Args:
    ----
    api: The API to use to add the statuses.
    context_urls: The list of toot URLs to add.
    """
    list_of_context_urls = list(context_urls)
    if len(list_of_context_urls) == 0:
        return
    logging.debug(f"Adding {len(list_of_context_urls)} context URLs")
    count = 0
    failed = 0
    already_added = 0
    posts_to_fetch = []
    if api.client.pgupdater is None:
        msg = "No PostgreSQL updater"
        raise ApiError(msg)
    cached_posts: dict[str, Status | None] = api.client.pgupdater.get_dict_from_cache(
        list_of_context_urls,
    )
    logging.debug(f"Got {len(cached_posts)} cached posts")
    for url in list_of_context_urls:
        logging.debug(f"Checking {url}")
        cached = cached_posts.get(url)
        if cached:
            cached_status_id = cached.get("id")
            if cached_status_id:
                already_added += 1
            else:
                logging.debug(f"Got status with no ID: {cached}")
                posts_to_fetch.append(url)
        else:
            logging.debug(f"Didn't get status for {url} from cache")
            posts_to_fetch.append(url)

    if posts_to_fetch:
        logging.debug(f"Fetching {len(posts_to_fetch)} posts")
        tasks = []
        for url in posts_to_fetch:
            logging.debug(f"Adding {url} to home server")
            tasks.append(
                api.get(url),
            )
        for task in asyncio.as_completed(tasks):
            try:
                result: Status = await task
                logging.debug(f"Got {result}")
                count += 1
                api.client.pgupdater.cache_status(result)
            except ApiError:
                failed += 1

    logging.info(
        f"\033[1mAdded {count} new statuses (with {failed} failures, {already_added} "
        f"already seen)\033[0m",
    )
