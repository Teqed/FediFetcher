"""Pull posts from a Mastodon server, using a token."""

import logging
from datetime import UTC, datetime, timedelta

from dateutil import parser

from fedifetcher import add_context, api_mastodon, getter_wrappers, getters, helpers
from fedifetcher.ordered_set import OrderedSet


def find_posts_by_token(
        token: str,
        seen_urls: OrderedSet,
        parsed_urls : dict[str, tuple[str | None, str | None]],
        replied_toot_server_ids: dict[str, str | None],
        all_known_users : OrderedSet,
        recently_checked_users : OrderedSet,
        known_followings : OrderedSet,
        ) -> OrderedSet:
    """Pull posts from a Mastodon server, using a token."""
    user_ids = []
    user_ids = list(api_mastodon.get_active_user_ids(
        helpers.arguments.server,
        token,
        helpers.arguments.reply_interval_in_hours,
        ))
    logging.debug(f"Found user IDs: {user_ids}")
    if helpers.arguments.reply_interval_in_hours > 0:
        """pull the context toots of toots user replied to, from their
        original server, and add them to the local server."""
        logging.info("Pulling context toots for replies")
        logging.debug("Found user ID")
        reply_toots = getter_wrappers.get_all_reply_toots(
            helpers.arguments.server,
            user_ids,
            token,
            seen_urls,
            helpers.arguments.reply_interval_in_hours,
        )
        logging.debug("Found reply toots")
        known_context_urls = getter_wrappers.get_all_known_context_urls(
            helpers.arguments.server,
            reply_toots,
            parsed_urls,
            )
        logging.debug("Found known context URLs")
        seen_urls.update(known_context_urls)
        replied_toot_ids = getter_wrappers.get_all_replied_toot_server_ids(
            helpers.arguments.server,
            reply_toots,
            replied_toot_server_ids,
            parsed_urls,
        )
        logging.debug("Found replied toot IDs")
        context_urls = getter_wrappers.get_all_context_urls(
            helpers.arguments.server,
            replied_toot_ids,
            )
        logging.debug("Found context URLs")
        add_context.add_context_urls(
            helpers.arguments.server,
            token,
            context_urls,
            seen_urls,
            )
        logging.debug("Added context URLs")
    if helpers.arguments.home_timeline_length > 0:
        """Do the same with any toots on the key owner's home timeline """
        logging.info("Pulling context toots for home timeline")
        timeline_toots = api_mastodon.get_timeline(
            "home",
            helpers.arguments.server,
            token,
            helpers.arguments.home_timeline_length,
            )
        logging.debug("Found home timeline toots")
        known_context_urls = getter_wrappers.get_all_known_context_urls(
            helpers.arguments.server,
            timeline_toots,
            parsed_urls,
            )
        logging.debug("Found known context URLs")
        add_context.add_context_urls(
            helpers.arguments.server,
            token,
            known_context_urls,
            seen_urls,
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
                toot_created_at = parser.parse(toot["created_at"])
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
                        these_users.append(toot["reblog"]["account"])
                        if(len(toot["reblog"]["mentions"])):
                            logging.debug("Found reblog mentions")
                            these_users += toot["reblog"]["mentions"]
                for user in these_users:
                    logging.debug(f"Checking user: {user}")
                    if user not in mentioned_users and \
                            user["acct"] not in all_known_users:
                        logging.debug(f"Adding user: {user}")
                        mentioned_users.append(user)
            logging.debug(f"Mentioned users: {len(mentioned_users)}")
            add_context.add_user_posts(
                helpers.arguments.server,
                token,
                getter_wrappers.filter_known_users(
                    mentioned_users,
                    all_known_users,
                    ),
                recently_checked_users,
                all_known_users,
                seen_urls,
                )
    logging.debug(f"Getting user ID from {user_ids}")
    user_id = user_ids[0] # TODO: This is a hack
    if not user_id:
        logging.debug("Could not get User ID, skipping followings/followers")
    else:
        logging.debug(f"Got User ID: {user_id}")
        if helpers.arguments.max_followings > 0:
            logging.info(
        f"Getting posts from last {helpers.arguments.max_followings} followings")
            followings = getter_wrappers.get_new_followings(
                helpers.arguments.server,
                user_id,
                helpers.arguments.max_followings,
                all_known_users,
                )
            add_context.add_user_posts(
                helpers.arguments.server,
                token, followings,
                known_followings,
                all_known_users,
                seen_urls,
                )
        if helpers.arguments.max_followers > 0:
            logging.info(
        f"Getting posts from last {helpers.arguments.max_followers} followers")
            followers = getter_wrappers.get_new_followers(
                helpers.arguments.server,
                user_id,
                helpers.arguments.max_followers,
                all_known_users,
                )
            add_context.add_user_posts(
                helpers.arguments.server,
                token,
                followers,
                recently_checked_users,
                all_known_users,
                seen_urls,
                )
    if helpers.arguments.max_follow_requests > 0:
        logging.info(
    f"Getting posts from last {helpers.arguments.max_follow_requests} follow requests")
        follow_requests = getter_wrappers.get_new_follow_requests(
                            helpers.arguments.server,
                            token,
                            helpers.arguments.max_follow_requests,
                            all_known_users,
                            )
        add_context.add_user_posts(
            helpers.arguments.server,
            token,
            follow_requests,
            recently_checked_users,
            all_known_users,
            seen_urls,
            )
    if helpers.arguments.from_notifications > 0:
        logging.info(
    f"Getting notifications for last {helpers.arguments.from_notifications} hours")
        notification_users = getter_wrappers.get_notification_users(
                                helpers.arguments.server,
                                token,
                                all_known_users,
                                helpers.arguments.from_notifications,
                                )
        add_context.add_user_posts(
            helpers.arguments.server,
            token,
            notification_users,
            recently_checked_users,
            all_known_users,
            seen_urls,
            )
    if helpers.arguments.max_bookmarks > 0:
        logging.info(
    f"Pulling replies to the last {helpers.arguments.max_bookmarks} bookmarks")
        bookmarks = getter_wrappers.get_bookmarks(
                        helpers.arguments.server,
                        token,
                        helpers.arguments.max_bookmarks,
                        )
        known_context_urls = getter_wrappers.get_all_known_context_urls(
                                helpers.arguments.server,
                                iter(bookmarks),
                                parsed_urls,
                                )
        add_context.add_context_urls(
            helpers.arguments.server,
            token,
            known_context_urls,
            seen_urls,
            )
    if helpers.arguments.max_favourites > 0:
        logging.info(
    f"Pulling replies to the last {helpers.arguments.max_favourites} favourites")
        favourites = getter_wrappers.get_favourites(
                        helpers.arguments.server,
                        token,
                        helpers.arguments.max_favourites,
                        )
        known_context_urls = getter_wrappers.get_all_known_context_urls(
                                helpers.arguments.server,
                                iter(favourites),
                                parsed_urls,
                                )
        add_context.add_context_urls(
            helpers.arguments.server,
            token,
            known_context_urls,
            seen_urls,
            )
    return seen_urls
