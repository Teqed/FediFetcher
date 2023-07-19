"""Add context toots to the server."""
import logging
from collections.abc import Iterable

from mastodon.types import Status

from fedifetcher import api_mastodon, getter_wrappers, parsers
from fedifetcher.ordered_set import OrderedSet
from fedifetcher.postgresql import PostgreSQLUpdater

from . import getters, helpers


async def add_user_posts( # noqa: PLR0913
        server: str,
        access_token: str,
        followings: list,
        know_followings: OrderedSet,
        all_known_users: OrderedSet,
        external_tokens: dict[str, str],
        pgupdater: PostgreSQLUpdater,
) -> None:
    """Add the given user's posts to the server.

    Args:
    ----
    server: The server to add the posts to.
    access_token: The access token to use to add the posts.
    followings: The list of users to add the posts of.
    know_followings: The list of users whose posts we already know.
    all_known_users: The list of all users whose posts we already know.
    external_tokens: A dict of external tokens, keyed by server. If None, no \
        external tokens will be used.
    pgupdater: The PostgreSQL updater.
    """
    for user in followings:
        if user["acct"] not in all_known_users and not user["url"].startswith(f"https://{server}/"):
            posts = await getters.get_user_posts(
                user, know_followings, server, external_tokens)

            if posts is not None:
                count = 0
                failed = 0
                already_added = 0
                list_of_post_urls = [post.get("url") for post in posts]
                list_of_post_urls = [url for url in list_of_post_urls if url]
                cached_posts: dict[str, Status | None] = pgupdater.get_dict_from_cache(
                                                                    list_of_post_urls)
                for post in posts:
                    post_url = post.get("url")
                    if post_url:
                        cached = cached_posts.get(post_url)
                        if cached:
                            already_added += 1
                            logging.debug(f"Already added {post_url}")
                            continue
                    if post.get("reblog") is None:
                        added = await add_post_with_context(
                            post, server, access_token,
                            external_tokens, pgupdater)
                        if added is True:
                            status = Status(
                                id=post.get("id"),
                                uri=post.get("uri"),
                                url=post.get("url"),
                                account=post.get("account"),
                                in_reply_to_id=post.get("in_reply_to_id"),
                                in_reply_to_account_id=post.get(
                                    "in_reply_to_account_id"),
                                reblog=post.get("reblog"),
                                content=post.get("content"),
                                created_at=post.get("created_at"),
                                reblogs_count=post.get("reblogs_count"),
                                favourites_count=post.get("favourites_count"),
                                reblogged=post.get("reblogged"),
                                favourited=post.get("favourited"),
                                sensitive=post.get("sensitive"),
                                spoiler_text=post.get("spoiler_text"),
                                visibility=post.get("visibility"),
                                mentions=post.get("mentions"),
                                media_attachments=post.get(
                                    "media_attachments"),
                                emojis=post.get("emojis"),
                                tags=post.get("tags"),
                                bookmarked=post.get("bookmarked"),
                                application=post.get("application"),
                                language=post.get("language"),
                                muted=post.get("muted"),
                                pinned=post.get("pinned"),
                                replies_count=post.get("replies_count"),
                                card=post.get("card"),
                                poll=post.get("poll"),
                                edited_at=post.get("edited_at"),
                            )
                            pgupdater.cache_status(status)
                            count += 1
                        else:
                            failed += 1
                logging.info(
f"Added {count} posts for user {user['acct']} with {failed} errors and \
{already_added} already seen",
                )
                if failed == 0:
                    know_followings.add(user["acct"])
                    all_known_users.add(user["acct"])

async def add_post_with_context(
        post : dict[str, str],
        server : str,
        access_token : str,
        external_tokens : dict[str, str],
        pgupdater : PostgreSQLUpdater,
        ) -> bool:
    """Add the given post to the server.

    Args:
    ----
    post: The post to add.
    server: The server to add the post to.
    access_token: The access token to use to add the post.
    external_tokens: A dict of external tokens, keyed by server. If None, no \
        external tokens will be used.
    pgupdater: The PostgreSQL updater.

    Returns:
    -------
    bool: True if the post was added successfully, False otherwise.
    """
    added = await api_mastodon.add_context_url(post["url"], server, access_token)
    if added is not False:
        pgupdater.cache_status(added)
        if ("replies_count" in post or "in_reply_to_id" in post) and getattr(
                helpers.arguments, "backfill_with_context", 0) > 0:
            parsed_urls : dict[str, tuple[str | None, str | None]] = {}
            parsed = parsers.post(post["url"], parsed_urls)
            if parsed is not None and parsed[0] is not None:
                known_context_urls = await \
                    getter_wrappers.get_all_known_context_urls(
                    server, iter((post,)), parsed_urls, external_tokens, pgupdater,
                    access_token)
                (await add_context_urls(
                    server, access_token, known_context_urls, pgupdater))
        return True

    return False

async def add_context_urls(
        server : str,
        access_token : str,
        context_urls : Iterable[str],
        pgupdater : PostgreSQLUpdater,
        ) -> None:
    """Add the given toot URLs to the server.

    Args:
    ----
    server: The server to add the toots to.
    access_token: The access token to use to add the toots.
    context_urls: The list of toot URLs to add.
    pgupdater: The PostgreSQL updater.
    """
    list_of_context_urls = list(context_urls)
    logging.debug(f"Adding {len(list_of_context_urls)} context URLs")
    count = 0
    failed = 0
    already_added = 0
    posts_to_fetch = []
    cached_posts: dict[str, Status | None] = \
        pgupdater.get_dict_from_cache(list_of_context_urls)
    logging.debug(f"Got {len(cached_posts)} cached posts")
    for url in context_urls:
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
        for url in posts_to_fetch:
            logging.info(f"Fetching {url} through {server}")
            status_added = await api_mastodon.add_context_url(
                url, server, access_token)
            if status_added:
                pgupdater.cache_status(status_added)
                count += 1
            else:
                failed += 1
                logging.warning(f"Failed {url}")
                failed += 1

    logging.info(f"\033[1mAdded {count} new statuses (with {failed} failures, \
{already_added} already seen)\033[0m")
