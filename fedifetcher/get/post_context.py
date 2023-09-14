"""Get the URLs of the context toots of the given toot."""
import asyncio
import logging

from fedifetcher.api.lemmy import api_lemmy
from fedifetcher.api.mastodon import api_mastodon
from fedifetcher.api.postgresql import PostgreSQLUpdater


async def post_content(  # noqa: PLR0913, D417
    server: str,
    toot_id: str,
    toot_url: str,
    external_tokens: dict[str, str],
    pgupdater: PostgreSQLUpdater,
    home_server: str,
    home_server_token: str,
    semaphore: asyncio.Semaphore | None = None,
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
    if semaphore is None:
        semaphore = asyncio.Semaphore(1)
    async with semaphore:
        logging.debug(f"Getting context for toot {toot_url} from {server}")
        try:
            external_token = external_tokens.get(server)

            if toot_url.find("/comment/") != -1:
                logging.debug("Getting comment context")
                return api_lemmy.get_comment_context(server, toot_id, toot_url)

            if toot_url.find("/post/") != -1:
                logging.debug("Getting post context")
                return api_lemmy.get_comments_urls(server, toot_id, toot_url)

            if toot_url.find("/notes/") != -1:
                logging.debug("Getting note ID")
                # This is a Calckey / Firefish post.
                # We need to get the Mastodon-compatible ID.
                # We can do this by getting the post from the home server.
                _status = await api_mastodon.Mastodon(server, external_token).search_v2(
                    toot_url,
                )
                if _status:
                    _fake_id = _status.get("id")
                    if _fake_id:
                        toot_id = _fake_id
                else:
                    # The Calckey API is out of date and requires auth on this endpoint.
                    logging.warning(
                        f"Couldn't get Mastodon-compatible ID for {toot_url}",
                    )
                    return []

            logging.debug("Getting Mastodon context")
            return await api_mastodon.Mastodon(server, external_token).get_remote_status_context(
                toot_id,
                home_server,
                home_server_token,
                pgupdater,
            )

        except Exception:
            logging.exception(f"Error getting context for toot {toot_url}.")
            return []
