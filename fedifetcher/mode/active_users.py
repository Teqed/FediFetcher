"""Get posts of users which have active IDs on the local server."""
import logging

from fedifetcher import find_context, getter_wrappers
from fedifetcher.api.mastodon.api_mastodon import Mastodon


async def active_users(
        replied_toot_server_ids, parsed_urls, admin_token,
        external_tokens, pgupdater, arguments) -> None:
    """Get posts of users which have active IDs on the local server."""
    user_ids = list(await Mastodon(arguments.server,
                admin_token, pgupdater).get_active_user_ids(
                arguments.reply_interval_in_hours))
    logging.debug(f"Found user IDs: {user_ids}")
    """pull the context toots of toots user replied to, from their
            original server, and add them to the local server."""
    logging.info("Pulling context toots for replies")
    logging.debug("Found user ID, getting reply toots")
    reply_toots = await getter_wrappers.get_all_reply_toots(
                arguments.server,
                user_ids,
                admin_token,
                pgupdater,
                arguments.reply_interval_in_hours,
            )
    logging.debug("Found reply toots, getting known context URLs")
    await getter_wrappers.get_all_known_context_urls(
                arguments.server,
                reply_toots,
                parsed_urls,
                external_tokens,
                pgupdater,
                admin_token,
                )
    logging.debug("Found known context URLs, getting replied toot IDs")
    replied_toot_ids = getter_wrappers.get_all_replied_toot_server_ids(
                arguments.server,
                reply_toots,
                replied_toot_server_ids,
                parsed_urls,
            )
    logging.debug("Found replied toot IDs, getting context URLs")
    context_urls = await getter_wrappers.get_all_context_urls(
                arguments.server,
                replied_toot_ids,
                external_tokens,
                pgupdater,
                arguments.server,
                admin_token,
            )
    logging.debug("Found context URLs, adding context URLs")
    await find_context.add_context_urls_wrapper(
                arguments.server,
                admin_token,
                context_urls,
                pgupdater,
            )
    logging.debug("Added context URLs")
