"""Add context toots to the server."""
import logging
from collections.abc import Iterable

from fedifetcher import api_mastodon, getter_wrappers, parsers
from fedifetcher.ordered_set import OrderedSet
from fedifetcher.postgresql import PostgreSQLUpdater
from mastodon.types import Status

from . import getters, helpers


def add_user_posts( # noqa: PLR0913
        server: str,
        access_token: str,
        followings: list,
        know_followings: OrderedSet,
        all_known_users: OrderedSet,
        seen_urls: OrderedSet,
        external_tokens: dict[str, str],
        pgupdater: PostgreSQLUpdater,
        status_id_cache: dict[str, str],
) -> None:
    """Add the given user's posts to the server.

    Args:
    ----
    server: The server to add the posts to.
    access_token: The access token to use to add the posts.
    followings: The list of users to add the posts of.
    know_followings: The list of users whose posts we already know.
    all_known_users: The list of all users whose posts we already know.
    seen_urls: The list of all URLs we have already seen.
    external_tokens: A dict of external tokens, keyed by server. If None, no \
        external tokens will be used.
    """
    for user in followings:
        if user["acct"] not in all_known_users and not user["url"].startswith(f"https://{server}/"):
            posts = getters.get_user_posts(
                user, know_followings, server, external_tokens)

            if posts is not None:
                count = 0
                failed = 0
                for post in posts:
                    if post.get("reblog") is None and isinstance(post.get("url"), str) \
                            and str(post.get("url")) not in seen_urls:
                        added = add_post_with_context(
                            post, server, access_token, seen_urls,
                            external_tokens, pgupdater, status_id_cache)
                        if added is True:
                            seen_urls.add(str(post["url"]))
                            count += 1
                        else:
                            failed += 1
                logging.info(
                    f"Added {count} posts for user {user['acct']} with {failed} errors",
                )
                if failed == 0:
                    know_followings.add(user["acct"])
                    all_known_users.add(user["acct"])

def add_post_with_context(
        post : dict[str, str],
        server : str,
        access_token : str,
        seen_urls : OrderedSet,
        external_tokens : dict[str, str],
        pgupdater : PostgreSQLUpdater,
        status_id_cache : dict[str, str],
        ) -> bool:
    """Add the given post to the server.

    Args:
    ----
    post: The post to add.
    server: The server to add the post to.
    access_token: The access token to use to add the post.
    seen_urls: The list of all URLs we have already seen.

    Returns:
    -------
    bool: True if the post was added successfully, False otherwise.
    """
    added = api_mastodon.add_context_url(post["url"], server, access_token)
    if added is not False:
        seen_urls.add(post["url"])
        if ("replies_count" in post or "in_reply_to_id" in post) and getattr(
                helpers.arguments, "backfill_with_context", 0) > 0:
            parsed_urls : dict[str, tuple[str | None, str | None]] = {}
            parsed = parsers.post(post["url"], parsed_urls)
            if parsed is not None and parsed[0] is not None:
                known_context_urls = getter_wrappers.get_all_known_context_urls(
                    server, iter((post,)), parsed_urls, external_tokens, pgupdater,
                    access_token, status_id_cache)
                add_context_urls(server, access_token, known_context_urls, seen_urls)
        return True

    return False

def add_context_urls(
        server : str,
        access_token : str,
        context_urls : Iterable[str],
        seen_urls : OrderedSet,
        status_id_cache : dict[str, str] | None = None,
        parsed_urls : dict[str, tuple[str | None, str | None]] | None = None,
        ) -> None:
    """Add the given toot URLs to the server.

    Args:
    ----
    server: The server to add the toots to.
    access_token: The access token to use to add the toots.
    context_urls: The list of toot URLs to add.
    seen_urls: The list of all URLs we have already seen.
    status_id_cache: A dict of status IDs, keyed by URL. If None, no status \
        IDs will be cached.
    """
    logging.info("Adding statuses to server...")
    count = 0
    failed = 0
    for url in context_urls:
        if url not in seen_urls:
            parsed = parsers.post(url, parsed_urls)
            if status_id_cache is not None and parsed is not None \
                    and (f"{parsed[0],url}") in status_id_cache:
                added = True
            else:
                added = api_mastodon.add_context_url(url, server, access_token)
                if status_id_cache is not None and isinstance(added, Status) \
                        and added.url:
                    parsed = parsers.post(added.url, parsed_urls)
                    if parsed is not None and parsed[0] is not None:
                        status_id_cache[f"{parsed[0]},{added.url}"] = str(added.id)
            if added is not False:
                logging.info(f"Added {url}")
                seen_urls.add(url)
                count += 1
            else:
                logging.warning(f"Failed to add {url}")
                failed += 1

    logging.info(f"Added {count} new statuses (with {failed} failures)")
