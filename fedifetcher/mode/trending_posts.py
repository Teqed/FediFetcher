"""Get trending posts from supplied servers."""
import logging

from fedifetcher import find_context, getter_wrappers
from fedifetcher.api.mastodon.api_mastodon_types import Status
from fedifetcher.find_trending_posts import find_trending_posts


async def trending_posts(
    parsed_urls,
    admin_token,
    external_tokens,
    pgupdater,
    arguments,
) -> None:
    """Get trending posts from supplied servers."""
    external_feeds = arguments.external_feeds.split(",")
    logging.info("Getting trending posts")
    trending_posts = await find_trending_posts(
        arguments.server,
        admin_token,
        external_feeds,
        external_tokens,
        pgupdater,
    )
    logging.info(f"Found {len(trending_posts)} trending posts")
    trending_posts = [post for post in trending_posts if post["replies_count"] != 0]
    trending_posts_changed = []
    trending_post_url_list = [post["url"] for post in trending_posts]
    trending_posts_with_cache: dict[str, Status | None] = pgupdater.get_dict_from_cache(
        trending_post_url_list,
    )
    for post in trending_posts:
        post_url: str = post["url"]
        new_reply_count = int(post["replies_count"])
        cached = trending_posts_with_cache.get(post_url)
        old_reply_count = int(cached.get("replies_count")) if cached else None
        if new_reply_count > 0 and (
            (old_reply_count is None) or (new_reply_count > old_reply_count)
        ):
            trending_posts_changed.append(post)
            if cached:
                cached["replies_count"] = new_reply_count
                favourites_count = post.get("favourites_count") or 0
                cached["favourites_count"] = (
                    post.get("favourites_count")
                    if (int(favourites_count) > int(cached.get("favourites_count")))
                    else cached.get("favourites_count")
                )
                reblogs_count = post.get("reblogs_count") or 0
                cached["reblogs_count"] = (
                    post.get("reblogs_count")
                    if (int(reblogs_count) > int(cached.get("reblogs_count")))
                    else cached.get("reblogs_count")
                )
                cached["id"] = post.get("id")
                pgupdater.cache_status(cached)
            else:
                status = Status(
                    id=post.get("id"),
                    uri=post.get("uri"),
                    url=post.get("url"),
                    account=post.get("account"),
                    in_reply_to_id=post.get("in_reply_to_id"),
                    in_reply_to_account_id=post.get("in_reply_to_account_id"),
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
                    media_attachments=post.get("media_attachments"),
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
    logging.info(
        f"Found {len(trending_posts_changed)} trending posts with new replies, getting "
        f"known context URLs",
    )
    known_context_urls = await getter_wrappers.get_all_known_context_urls(
        arguments.server,
        trending_posts_changed,
        parsed_urls,
        external_tokens,
        pgupdater,
        admin_token,
    )
    known_context_urls = list(known_context_urls)
    logging.debug(
        f"Found {len(known_context_urls)} known context URLs, getting context URLs",
    )
    await find_context.add_context_urls_wrapper(
        arguments.server,
        admin_token,
        known_context_urls,
        pgupdater,
    )
    logging.debug("Added context URLs")
