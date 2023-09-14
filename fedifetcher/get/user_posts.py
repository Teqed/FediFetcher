"""Get a list of posts from a user."""
import logging
import re

from fedifetcher import parsers
from fedifetcher.api.lemmy import api_lemmy
from fedifetcher.api.mastodon import api_mastodon
from fedifetcher.helpers.ordered_set import OrderedSet


async def user_posts(
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
        _external_token = (
            external_tokens.get(parsed_url[0]) if external_tokens else None
        )
        user_id = await api_mastodon.Mastodon(
            parsed_url[0],
            _external_token,
        ).get_user_id(parsed_url[1])
        logging.debug(f"User ID: {user_id}")
    except Exception:
        logging.exception(f"Error getting user ID for user {user['acct']}")
        return None

    if not parsed_url[0] or not user_id:
        return None

    return await api_mastodon.Mastodon(parsed_url[0]).get_user_statuses(user_id)
