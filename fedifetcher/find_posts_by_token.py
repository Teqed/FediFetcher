"""Pull posts from a Mastodon server, using a token."""

import logging
from datetime import UTC, datetime, timedelta
from typing import cast

from fedifetcher import add_context, api_mastodon, getter_wrappers, helpers
from fedifetcher.ordered_set import OrderedSet
from fedifetcher.postgresql import PostgreSQLUpdater


async def find_posts_by_token( # pylint: disable=too-many-arguments # pylint: disable=too-many-locals # noqa: C901, E501, PLR0915, PLR0912, PLR0913
        token: str,
        parsed_urls : dict[str, tuple[str | None, str | None]],
        replied_toot_server_ids: dict[str, str | None],
        all_known_users : OrderedSet,
        recently_checked_users : OrderedSet,
        known_followings : OrderedSet,
        external_tokens: dict[str, str],
        pgupdater: PostgreSQLUpdater,
        ) -> None:
    """Pull posts from a Mastodon server, using a token."""
    logging.info("Finding posts for provided token")
    if helpers.arguments.home_timeline_length > 0:
        """Do the same with any toots on the key owner's home timeline """
        logging.info("Pulling context toots for home timeline")
        timeline_toots = await api_mastodon.get_timeline(
            helpers.arguments.server,
            token,
            "home",
            helpers.arguments.home_timeline_length,
            )
        logging.debug("Found home timeline toots, getting context URLs")
        known_context_urls = await getter_wrappers.get_all_known_context_urls(
            helpers.arguments.server,
            timeline_toots,
            parsed_urls,
            external_tokens,
            pgupdater,
            token,
            )
        logging.debug("Found known context URLs, getting context URLs")
        await add_context.add_context_urls(
            helpers.arguments.server,
            token,
            known_context_urls,
            pgupdater,
            )
        logging.debug("Added context URLs")
        # Backfill any post authors, and any mentioned users
        if helpers.arguments.backfill_mentioned_users > 0:
            logging.info(
f"Backfilling posts from last {helpers.arguments.backfill_mentioned_users} \
mentioned users")
            mentioned_users = []
            cut_off = datetime.now(
                datetime.now(UTC).astimezone().tzinfo) - timedelta(minutes=60)
            logging.debug(f"Cut off: {cut_off}")
            for toot in timeline_toots:
                logging.debug(f"Checking toot: {toot}")
                these_users = []
                toot_created_at = cast(datetime, toot["created_at"])
                user_limit = {
                    "precutoff": 10,
                    "postcutoff": 30,
                }
                if len(mentioned_users) < user_limit["precutoff"] or (
                        toot_created_at > cut_off and \
                            len(mentioned_users) < user_limit["postcutoff"]):
                    these_users.append(toot["account"])
                    if(len(toot["mentions"])):
                        logging.debug("Found mentions")
                        these_users += toot["mentions"]
                    if(toot["reblog"]):
                        logging.debug("Found reblog")
                        _reblog = cast(dict, toot["reblog"])
                        _account = _reblog["account"]
                        _mentions = _reblog["mentions"]
                        these_users.append(_account)
                        if(len(_mentions)):
                            logging.debug("Found reblog mentions")
                            these_users += _mentions
                for user in these_users:
                    logging.debug(f"Checking user: {user}")
                    if user not in mentioned_users and \
                            user["acct"] not in all_known_users:
                        logging.debug(f"Adding user: {user}")
                        mentioned_users.append(user)
            logging.debug(f"Mentioned users: {len(mentioned_users)}")
            await add_context.add_user_posts(
                helpers.arguments.server,
                token,
                getter_wrappers.filter_known_users(
                    mentioned_users,
                    all_known_users,
                    ),
                recently_checked_users,
                all_known_users,
                external_tokens,
                pgupdater,
                )
    token_user_id = await api_mastodon.get_me(helpers.arguments.server, token)
    if not token_user_id:
        logging.debug("Could not get User ID, skipping replies/followings/followers")
    else:
        logging.debug(f"Got User ID: {token_user_id}")
        if helpers.arguments.reply_interval_in_hours > 0:
            """pull the context toots of toots user replied to, from their
            original server, and add them to the local server."""
            logging.info("Pulling context toots for replies")
            reply_toots = await getter_wrappers.get_all_reply_toots(
                helpers.arguments.server,
                [token_user_id],
                token,
                pgupdater,
                helpers.arguments.reply_interval_in_hours,
            )
            logging.debug("Found reply toots, getting context URLs")
            await getter_wrappers.get_all_known_context_urls(
                helpers.arguments.server,
                reply_toots,
                parsed_urls,
                external_tokens,
                pgupdater,
                token,
                )
            logging.debug("Found known context URLs, getting context URLs")
            replied_toot_ids = getter_wrappers.get_all_replied_toot_server_ids(
                helpers.arguments.server,
                reply_toots,
                replied_toot_server_ids,
                parsed_urls,
            )
            logging.debug("Found replied toot IDs, getting context URLs")
            context_urls = await getter_wrappers.get_all_context_urls(
                helpers.arguments.server,
                replied_toot_ids,
                external_tokens,
                pgupdater,
                helpers.arguments.server,
                token,
                )
            logging.debug("Found context URLs, getting context URLs")
            await add_context.add_context_urls(
                helpers.arguments.server,
                token,
                context_urls,
                pgupdater,
                )
            logging.debug("Added context URLs")
        if helpers.arguments.max_followings > 0:
            logging.info(
        f"Getting posts from last {helpers.arguments.max_followings} followings")
            followings = await getter_wrappers.get_new_followings(
                helpers.arguments.server,
                token,
                token_user_id,
                helpers.arguments.max_followings,
                all_known_users,
                )
            logging.debug("Got followings, getting context URLs")
            await add_context.add_user_posts(
                helpers.arguments.server,
                token, followings,
                known_followings,
                all_known_users,
                external_tokens,
                pgupdater,
                )
            logging.debug("Added context URLs")
        if helpers.arguments.max_followers > 0:
            logging.info(
        f"Getting posts from last {helpers.arguments.max_followers} followers")
            followers = await getter_wrappers.get_new_followers(
                helpers.arguments.server,
                token,
                token_user_id,
                helpers.arguments.max_followers,
                all_known_users,
                )
            logging.debug("Got followers, getting context URLs")
            await add_context.add_user_posts(
                helpers.arguments.server,
                token,
                followers,
                recently_checked_users,
                all_known_users,
                external_tokens,
                pgupdater,
                )
            logging.debug("Added context URLs")
    if helpers.arguments.max_follow_requests > 0:
        logging.info(
    f"Getting posts from last {helpers.arguments.max_follow_requests} follow requests")
        follow_requests = await getter_wrappers.get_new_follow_requests(
                            helpers.arguments.server,
                            token,
                            helpers.arguments.max_follow_requests,
                            all_known_users,
                            )
        logging.debug("Got follow requests, getting context URLs")
        await add_context.add_user_posts(
            helpers.arguments.server,
            token,
            follow_requests,
            recently_checked_users,
            all_known_users,
            external_tokens,
            pgupdater,
            )
        logging.debug("Added context URLs")
    if helpers.arguments.from_notifications > 0:
        logging.info(
    f"Getting notifications for last {helpers.arguments.from_notifications} hours")
        notification_users = await getter_wrappers.get_notification_users(
                                helpers.arguments.server,
                                token,
                                all_known_users,
                                helpers.arguments.from_notifications,
                                )
        logging.debug("Got notification users, getting context URLs")
        await add_context.add_user_posts(
            helpers.arguments.server,
            token,
            notification_users,
            recently_checked_users,
            all_known_users,
            external_tokens,
            pgupdater,
            )
        logging.debug("Added context URLs")
    if helpers.arguments.max_bookmarks > 0:
        logging.info(
    f"Pulling replies to the last {helpers.arguments.max_bookmarks} bookmarks")
        bookmarks = await api_mastodon.get_bookmarks(
                        helpers.arguments.server,
                        token,
                        helpers.arguments.max_bookmarks,
                        )
        logging.debug("Got bookmarks, getting context URLs")
        known_context_urls = await getter_wrappers.get_all_known_context_urls(
                                helpers.arguments.server,
                                iter(bookmarks),
                                parsed_urls,
                                external_tokens,
                                pgupdater,
                                token,
                                )
        logging.debug("Got known context URLs, getting context URLs")
        await add_context.add_context_urls(
            helpers.arguments.server,
            token,
            known_context_urls,
            pgupdater,
            )
        logging.debug("Added context URLs")
    if helpers.arguments.max_favourites > 0:
        logging.info(
    f"Pulling replies to the last {helpers.arguments.max_favourites} favourites")
        favourites = await api_mastodon.get_favourites(
                        helpers.arguments.server,
                        token,
                        helpers.arguments.max_favourites,
                        )
        logging.debug("Got favourites, getting context URLs")
        known_context_urls = await getter_wrappers.get_all_known_context_urls(
                                helpers.arguments.server,
                                iter(favourites),
                                parsed_urls,
                                external_tokens,
                                pgupdater,
                                token,
                                )
        logging.debug("Got known context URLs, getting context URLs")
        await add_context.add_context_urls(
            helpers.arguments.server,
            token,
            known_context_urls,
            pgupdater,
            )
        logging.debug("Added context URLs")
