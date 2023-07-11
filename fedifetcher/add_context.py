"""Add context toots to the server."""
import logging
from collections.abc import Iterable

from fedifetcher import api_mastodon, getter_wrappers, parsers
from fedifetcher.ordered_set import OrderedSet

from . import getters, helpers


def add_user_posts( # noqa: PLR0913
        server: str,
        access_token: str,
        followings: list,
        know_followings: OrderedSet,
        all_known_users: OrderedSet,
        seen_urls: OrderedSet,
        external_tokens: dict[str, str] | None,
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
                            post, server, access_token, seen_urls)
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
            if parsed is None:
                return True
            known_context_urls = getter_wrappers.get_all_known_context_urls(
                server, iter((post,)), parsed_urls)
            add_context_urls(server, access_token, known_context_urls, seen_urls)
        return True

    return False

def add_context_urls(
        server : str,
        access_token : str,
        context_urls : Iterable[str],
        seen_urls : OrderedSet,
        ) -> None:
    """Add the given toot URLs to the server.

    Args:
    ----
    server: The server to add the toots to.
    access_token: The access token to use to add the toots.
    context_urls: The list of toot URLs to add.
    seen_urls: The list of all URLs we have already seen.
    """
    count = 0
    failed = 0
    for url in context_urls:
        if url not in seen_urls:
            logging.info(f"Adding context for {url}")
            added = api_mastodon.add_context_url(url, server, access_token)
            if added is not False:
                seen_urls.add(url)
                count += 1
            else:
                failed += 1

    logging.info(f"Added {count} new context toots (with {failed} failures)")
