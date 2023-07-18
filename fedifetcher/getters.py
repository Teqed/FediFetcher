"""Functions to get data from Fediverse servers."""
import logging
import re

from fedifetcher.ordered_set import OrderedSet
from fedifetcher.postgresql import PostgreSQLUpdater

from . import api_lemmy, api_mastodon, parsers


async def get_user_posts(
        user: dict[str, str],
        know_followings: OrderedSet,
        server: str,
        external_tokens: dict[str, str] | None,
) -> list[dict[str, str]] | None:
    """Get a list of posts from a user.

    Args:
    ----
    user (dict): The user to get the posts from.
    know_followings (set[str]): A set of known followings.
    server (str): The local server, to check if the user is local.
    external_tokens (dict[str, str] | None): A dict of external tokens, \
        keyed by server. If None, no external tokens will be used.

    Returns:
    -------
    list[dict] | None: A list of posts from the user, or None if the user \
        couldn't be fetched.

    """
    parsed_url = parsers.user(user["url"])

    if (parsed_url is None) or (parsed_url[0] == server):
        know_followings.add(user["acct"])
        return None

    if re.match(r"^https:\/\/[^\/]+\/c\/", user["url"]):
        return api_lemmy.get_community_posts_from_url(parsed_url)

    if re.match(r"^https:\/\/[^\/]+\/u\/", user["url"]):
        return api_lemmy.get_user_posts_from_url(parsed_url)

    try:
        logging.info(f"Getting user ID for user {user['acct']}")
        _external_token = external_tokens.get(parsed_url[0]) \
            if external_tokens else None
        user_id = await api_mastodon.get_user_id(
            parsed_url[1], parsed_url[0], _external_token)
        logging.debug(f"User ID: {user_id}")
    except Exception:
        logging.exception(f"Error getting user ID for user {user['acct']}")
        return None

    if not parsed_url[0] or not user_id:
        return None

    return await api_mastodon.get_user_posts_from_id(user_id, parsed_url[0])

async def get_post_context(  # noqa: PLR0913, D417
        server: str,
        toot_id: str,
        toot_url: str,
        external_tokens: dict[str, str],
        pgupdater: PostgreSQLUpdater,
        home_server: str,
        home_server_token: str,
) -> list[str]:
    """Get the URLs of the context toots of the given toot asynchronously.

    Args:
    ----
    server (str): The server to get the context toots from.
    toot_id (str): The ID of the toot to get the context toots for.
    toot_url (str): The URL of the toot to get the context toots for.

    Returns:
    -------
    list[str]: The URLs of the context toots of the given toot.
    """
    try:
        external_token = external_tokens.get(server)

        if toot_url.find("/comment/") != -1:
            return api_lemmy.get_comment_context(server, toot_id, toot_url)

        if toot_url.find("/post/") != -1:
            return api_lemmy.get_comments_urls(server, toot_id, toot_url)

        return await api_mastodon.get_toot_context(
            server, toot_id, external_token, pgupdater,
            home_server, home_server_token,
        )


    except Exception as ex:
        logging.error(f"Error getting context for toot {toot_url}. Exception: {ex}")
        return []
