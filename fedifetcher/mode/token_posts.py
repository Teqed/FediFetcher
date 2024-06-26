"""Pull posts from a Mastodon server, using a token."""

import logging
from argparse import Namespace
from datetime import UTC, datetime, timedelta
from typing import cast

from fedifetcher import find_context, getter_wrappers
from fedifetcher.api.mastodon import api_mastodon
from fedifetcher.api.postgresql import PostgreSQLUpdater
from fedifetcher.find_user_posts import add_user_posts
from fedifetcher.helpers.ordered_set import OrderedSet


async def token_posts(  # pylint: disable=too-many-arguments # pylint: disable=too-many-locals # noqa: C901, E501, PLR0915, PLR0912, PLR0913
    token: str,
    parsed_urls: dict[str, tuple[str | None, str | None]],
    replied_toot_server_ids: dict[str, str | None],
    all_known_users: OrderedSet,
    recently_checked_users: OrderedSet,
    known_followings: OrderedSet,
    external_tokens: dict[str, str],
    pgupdater: PostgreSQLUpdater,
    arguments: Namespace,
) -> None:
    """Pull posts from a Mastodon server, using a token."""
    logging.info("Finding posts for provided token")
    if arguments.home_timeline_length > 0:
        """Do the same with any toots on the key owner's home timeline"""
        logging.info("Pulling context toots for home timeline")
        timeline_toots = await api_mastodon.Mastodon(
            arguments.server,
            token,
            pgupdater,
        ).get_home_timeline(arguments.home_timeline_length)
        logging.debug("Found home timeline toots, getting context URLs")
        known_context_urls = await getter_wrappers.get_all_known_context_urls(
            arguments.server,
            timeline_toots,
            parsed_urls,
            external_tokens,
            pgupdater,
            token,
        )
        logging.debug("Found known context URLs, getting context URLs")
        await find_context.add_context_urls_wrapper(
            arguments.server,
            token,
            known_context_urls,
            pgupdater,
        )
        logging.debug("Added context URLs")
        # Backfill any post authors, and any mentioned users
        if arguments.backfill_mentioned_users > 0:
            logging.info(
                f"Backfilling posts from last {arguments.backfill_mentioned_users} "
                f"mentioned users",
            )
            mentioned_users = []
            cut_off = datetime.now(datetime.now(UTC).astimezone().tzinfo) - timedelta(
                minutes=60,
            )
            logging.debug(f"Cut off: {cut_off}")
            for toot in timeline_toots:
                logging.debug(f"Checking toot: {toot.get('url')}")
                these_users = []
                toot_created_at = datetime.strptime(
                    toot["created_at"],
                    "%Y-%m-%dT%H:%M:%S.%fZ",
                ).replace(tzinfo=UTC)
                user_limit = {
                    "precutoff": 10,
                    "postcutoff": 30,
                }
                if len(mentioned_users) < user_limit["precutoff"] or (
                    toot_created_at > cut_off
                    and len(mentioned_users) < user_limit["postcutoff"]
                ):
                    these_users.append(toot["account"])
                    if len(toot["mentions"]):
                        logging.debug("Found mentions")
                        these_users += toot["mentions"]
                    if toot["reblog"]:
                        logging.debug("Found reblog")
                        _reblog = cast(dict, toot["reblog"])
                        _account = _reblog["account"]
                        _mentions = _reblog["mentions"]
                        these_users.append(_account)
                        if len(_mentions):
                            logging.debug("Found reblog mentions")
                            these_users += _mentions
                for user in these_users:
                    logging.debug(f"Checking user: {user.get('acct')}")
                    if (
                        user not in mentioned_users
                        and user["acct"] not in all_known_users
                    ):
                        logging.debug(f"Adding user: {user.get('acct')}")
                        mentioned_users.append(user)
            logging.debug(f"Mentioned users: {len(mentioned_users)}")
            await add_user_posts(
                arguments.server,
                token,
                getter_wrappers.filter_known_users(
                    mentioned_users,
                    all_known_users,
                ),
                recently_checked_users,
                all_known_users,
                external_tokens,
                pgupdater,
                arguments,
            )
    token_user_id = await api_mastodon.Mastodon(
        arguments.server,
        token,
        pgupdater,
    ).get_me()
    if not token_user_id:
        logging.debug("Could not get User ID, skipping replies/followings/followers")
    else:
        logging.debug(f"Got User ID: {token_user_id}")
        if arguments.reply_interval_in_hours > 0:
            """pull the context toots of toots user replied to, from their
            original server, and add them to the local server."""
            logging.info("Pulling context toots for replies")
            reply_toots = await getter_wrappers.get_all_reply_toots(
                arguments.server,
                [token_user_id],
                token,
                pgupdater,
                arguments.reply_interval_in_hours,
            )
            logging.debug("Found reply toots, getting context URLs")
            await getter_wrappers.get_all_known_context_urls(
                arguments.server,
                reply_toots,
                parsed_urls,
                external_tokens,
                pgupdater,
                token,
            )
            logging.debug("Found known context URLs, getting context URLs")
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
                token,
            )
            logging.debug("Found context URLs, getting context URLs")
            await find_context.add_context_urls_wrapper(
                arguments.server,
                token,
                context_urls,
                pgupdater,
            )
            logging.debug("Added context URLs")
        if arguments.max_followings > 0:
            logging.info(
                f"Getting posts from last {arguments.max_followings} followings",
            )
            followings = await getter_wrappers.get_new_followings(
                arguments.server,
                token,
                token_user_id,
                arguments.max_followings,
                all_known_users,
            )
            logging.debug("Got followings, getting context URLs")
            await add_user_posts(
                arguments.server,
                token,
                followings,
                known_followings,
                all_known_users,
                external_tokens,
                pgupdater,
                arguments,
            )
            logging.debug("Added context URLs")
        if arguments.max_followers > 0:
            logging.info(f"Getting posts from last {arguments.max_followers} followers")
            followers = await getter_wrappers.get_new_followers(
                arguments.server,
                token,
                token_user_id,
                arguments.max_followers,
                all_known_users,
            )
            logging.debug("Got followers, getting context URLs")
            await add_user_posts(
                arguments.server,
                token,
                followers,
                recently_checked_users,
                all_known_users,
                external_tokens,
                pgupdater,
                arguments,
            )
            logging.debug("Added context URLs")
    if arguments.max_follow_requests > 0:
        logging.info(
            f"Getting posts from last {arguments.max_follow_requests} follow requests",
        )
        follow_requests = await getter_wrappers.get_new_follow_requests(
            arguments.server,
            token,
            arguments.max_follow_requests,
            all_known_users,
        )
        logging.debug("Got follow requests, getting context URLs")
        await add_user_posts(
            arguments.server,
            token,
            follow_requests,
            recently_checked_users,
            all_known_users,
            external_tokens,
            pgupdater,
            arguments,
        )
        logging.debug("Added context URLs")
    if arguments.from_notifications > 0:
        logging.info(
            f"Getting notifications for last {arguments.from_notifications} hours",
        )
        notification_users = await getter_wrappers.get_notification_users(
            arguments.server,
            token,
            all_known_users,
            arguments.from_notifications,
        )
        logging.debug("Got notification users, getting context URLs")
        await add_user_posts(
            arguments.server,
            token,
            notification_users,
            recently_checked_users,
            all_known_users,
            external_tokens,
            pgupdater,
            arguments,
        )
        logging.debug("Added context URLs")
    if arguments.max_bookmarks > 0:
        logging.info(f"Pulling replies to the last {arguments.max_bookmarks} bookmarks")
        bookmarks = await api_mastodon.Mastodon(
            arguments.server,
            token,
            pgupdater,
        ).get_bookmarks(arguments.max_bookmarks)
        logging.debug("Got bookmarks, getting context URLs")
        known_context_urls = await getter_wrappers.get_all_known_context_urls(
            arguments.server,
            list(bookmarks),
            parsed_urls,
            external_tokens,
            pgupdater,
            token,
        )
        logging.debug("Got known context URLs, getting context URLs")
        await find_context.add_context_urls_wrapper(
            arguments.server,
            token,
            known_context_urls,
            pgupdater,
        )
        logging.debug("Added context URLs")
    if arguments.max_favourites > 0:
        logging.info(
            f"Pulling replies to the last {arguments.max_favourites} favourites",
        )
        favourites = await api_mastodon.Mastodon(
            arguments.server,
            token,
            pgupdater,
        ).get_favourites(
            arguments.max_favourites,
        )
        logging.debug("Got favourites, getting context URLs")
        known_context_urls = await getter_wrappers.get_all_known_context_urls(
            arguments.server,
            list(favourites),
            parsed_urls,
            external_tokens,
            pgupdater,
            token,
        )
        logging.debug("Got known context URLs, getting context URLs")
        await find_context.add_context_urls_wrapper(
            arguments.server,
            token,
            known_context_urls,
            pgupdater,
        )
        logging.debug("Added context URLs")
