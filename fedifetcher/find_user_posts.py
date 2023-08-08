"""Find user posts to the server."""
import logging
from argparse import Namespace

from fedifetcher import get
from fedifetcher.api.mastodon.api_mastodon_types import Status
from fedifetcher.api.postgresql import PostgreSQLUpdater
from fedifetcher.find_context import add_post_with_context
from fedifetcher.helpers.ordered_set import OrderedSet


async def add_user_posts( # noqa: PLR0913
        home_server: str,
        access_token: str,
        followings: list[dict[str, str]],
        know_followings: OrderedSet,
        all_known_users: OrderedSet,
        external_tokens: dict[str, str],
        pgupdater: PostgreSQLUpdater,
        arguments: Namespace,
) -> None:
    """Add the given user's posts to the server.

    Args:
    ----
    home_server: The server to add the posts to.
    access_token: The access token to use to add the posts.
    followings: The list of users to add the posts of.
    know_followings: The list of users whose posts we already know.
    all_known_users: The list of all users whose posts we already know.
    external_tokens: A dict of external tokens, keyed by server. If None, no \
        external tokens will be used.
    pgupdater: The PostgreSQL updater.
    """
    for user in followings:
        if user["acct"] not in all_known_users and not user["url"].startswith(f"https://{home_server}/"):
            posts = await get.user_posts(
                user, know_followings, home_server, external_tokens)

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
                            post, home_server, access_token,
                            external_tokens, pgupdater, arguments)
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
