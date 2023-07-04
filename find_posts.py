#!/usr/bin/env python3
"""FediFetcher - a tool to fetch posts from the fediverse."""

import json
import logging
import re
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dateutil import parser

import fedifetcher.helpers as helper
from fedifetcher import add_context, getters
from fedifetcher.ordered_set import OrderedSet

if __name__ == "__main__":
    start = datetime.now(UTC)

    logging.info("Starting FediFetcher")
    logging.debug(f"Arguments: {helper.arguments}")

    if(helper.arguments.config):
        if Path(helper.arguments.config).exists():
            with Path(helper.arguments.config).open(encoding="utf-8") as file:
                config = json.load(file)

            for key in config:
                setattr(helper.arguments, key.lower().replace("-","_"), config[key])

        else:
            logging.critical(f"Config file {helper.arguments.config} doesn't exist")
            sys.exit(1)

    if(helper.arguments.server is None or helper.arguments.access_token is None):
        logging.critical("You must supply at least a server name and an access token")
        sys.exit(1)

    # in case someone provided the server name as url instead,
    helper.arguments.server = re.sub(
        "^(https://)?([^/]*)/?$", "\\2", helper.arguments.server)


    run_id = uuid.uuid4()

    if(helper.arguments.on_start):
        try:
            helper.get(f"{helper.arguments.on_start}?rid={run_id}")
        except Exception as ex:
            logging.error(f"Error getting callback url: {ex}")

    if helper.arguments.lock_file is None:
        helper.arguments.lock_file = Path(helper.arguments.state_dir) / "lock.lock"
    LOCK_FILE = helper.arguments.lock_file

    if( Path(LOCK_FILE).exists()):
        logging.info(f"Lock file exists at {LOCK_FILE}")

        try:
            with Path(LOCK_FILE).open(encoding="utf-8") as file:
                lock_time = parser.parse(file.read())

            if (datetime.now(UTC) - lock_time).total_seconds() >= \
                    helper.arguments.lock_hours * 60 * 60:
                Path.unlink(LOCK_FILE)
                logging.info("Lock file has expired. Removed lock file.")
            else:
                logging.info(f"Lock file age is {datetime.now(UTC) - lock_time} - \
below --lock-hours={helper.arguments.lock_hours} provided.")
                if(helper.arguments.on_fail):
                    try:
                        helper.get(f"{helper.arguments.on_fail}?rid={run_id}")
                    except Exception as ex:
                        logging.error(f"Error getting callback url: {ex}")
                sys.exit(1)

        except Exception:
            logging.warning("Cannot read logfile age - aborting.")
            if(helper.arguments.on_fail):
                try:
                    helper.get(f"{helper.arguments.on_fail}?rid={run_id}")
                except Exception as ex:
                    logging.error(f"Error getting callback url: {ex}")
            sys.exit(1)

    with Path(LOCK_FILE).open("w", encoding="utf-8") as file:
        file.write(f"{datetime.now(UTC)}")

        seen_urls = OrderedSet()
        replied_toot_server_ids: dict[str, str | None] = {}
        known_followings = OrderedSet([])
        recently_checked_users = OrderedSet({})
    try:
        SEEN_URLS_FILE = Path(helper.arguments.state_dir) / "seen_urls"
        REPLIED_TOOT_SERVER_IDS_FILE = Path(
            helper.arguments.state_dir) / "replied_toot_server_ids"
        KNOWN_FOLLOWINGS_FILE = Path(helper.arguments.state_dir) / "known_followings"
        RECENTLY_CHECKED_USERS_FILE = Path(
            helper.arguments.state_dir) / "recently_checked_users"

        if Path(SEEN_URLS_FILE).exists():
            with Path(SEEN_URLS_FILE).open(encoding="utf-8") as file:
                seen_urls = OrderedSet(file.read().splitlines())

        if Path(REPLIED_TOOT_SERVER_IDS_FILE).exists():
            with Path(REPLIED_TOOT_SERVER_IDS_FILE).open(encoding="utf-8") as file:
                replied_toot_server_ids = json.load(file)

        if Path(KNOWN_FOLLOWINGS_FILE).exists():
            with Path(KNOWN_FOLLOWINGS_FILE).open(encoding="utf-8") as file:
                known_followings = OrderedSet(file.read().splitlines())

        if Path(RECENTLY_CHECKED_USERS_FILE).exists():
            with Path(RECENTLY_CHECKED_USERS_FILE).open(encoding="utf-8") as file:
                recently_checked_users = OrderedSet(list(json.load(file)))

        # Remove any users whose last check is too long in the past from the list
        for user in list(recently_checked_users):
            last_check = recently_checked_users.get_time(user)
            user_age = datetime.now(last_check.tzinfo) - last_check
            if(user_age.total_seconds(
            ) > helper.arguments.remember_users_for_hours * 60 * 60):
                recently_checked_users.remove(user)

        parsed_urls : dict[str, tuple[str | None, str | None]] = {}

        all_known_users = OrderedSet(
            list(known_followings) + list(recently_checked_users))

        if(isinstance(helper.arguments.access_token, str)):
            helper.arguments.access_token = [helper.arguments.access_token]

        for token in helper.arguments.access_token:

            if helper.arguments.reply_interval_in_hours > 0:
                """pull the context toots of toots user replied to, from their
                original server, and add them to the local server."""
                user_ids = getters.get_active_user_ids(
                    helper.arguments.server,
                    token,
                    helper.arguments.reply_interval_in_hours,
                    )
                reply_toots = getters.get_all_reply_toots(
                    helper.arguments.server,
                    user_ids,
                    token,
                    seen_urls,
                    helper.arguments.reply_interval_in_hours,
                )
                known_context_urls = getters.get_all_known_context_urls(
                    helper.arguments.server,
                    reply_toots,
                    parsed_urls,
                    )
                seen_urls.update(known_context_urls)
                replied_toot_ids = getters.get_all_replied_toot_server_ids(
                    helper.arguments.server,
                    reply_toots,
                    replied_toot_server_ids,
                    parsed_urls,
                )
                context_urls = getters.get_all_context_urls(
                    helper.arguments.server,
                    replied_toot_ids,
                    )
                add_context.add_context_urls(
                    helper.arguments.server,
                    token,
                    context_urls,
                    seen_urls,
                    )


            if helper.arguments.home_timeline_length > 0:
                """Do the same with any toots on the key owner's home timeline """
                timeline_toots = getters.get_timeline(
                    helper.arguments.server,
                    token,
                    helper.arguments.home_timeline_length,
                    )
                known_context_urls = getters.get_all_known_context_urls(
                    helper.arguments.server,
                    timeline_toots,
                    parsed_urls,
                    )
                add_context.add_context_urls(
                    helper.arguments.server,
                    token,
                    known_context_urls,
                    seen_urls,
                    )

                # Backfill any post authors, and any mentioned users
                if helper.arguments.backfill_mentioned_users > 0:
                    mentioned_users = []
                    cut_off = datetime.now(
                        datetime.now(UTC).astimezone().tzinfo) - timedelta(minutes=60)
                    for toot in timeline_toots:
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
                                these_users += toot["mentions"]
                            if(toot["reblog"]):
                                these_users.append(toot["reblog"]["account"])
                                if(len(toot["reblog"]["mentions"])):
                                    these_users += toot["reblog"]["mentions"]
                        for user in these_users:
                            if user not in mentioned_users and \
                                    user["acct"] not in all_known_users:
                                mentioned_users.append(user)

                    add_context.add_user_posts(
                        helper.arguments.server,
                        token,
                        getters.filter_known_users(
                            mentioned_users,
                            all_known_users,
                            ),
                        recently_checked_users,
                        all_known_users,
                        seen_urls,
                        )

            if helper.arguments.max_followings > 0:
                logging.info(
f"Getting posts from last {helper.arguments.max_followings} followings")
                user_id = getters.get_user_id(
                    helper.arguments.server,
                    helper.arguments.user,
                    token,
                    )
                followings = getters.get_new_followings(
                    helper.arguments.server,
                    user_id,
                    helper.arguments.max_followings,
                    all_known_users,
                    )
                add_context.add_user_posts(
                    helper.arguments.server,
                    token, followings,
                    known_followings,
                    all_known_users,
                    seen_urls,
                    )

            if helper.arguments.max_followers > 0:
                logging.info(
f"Getting posts from last {helper.arguments.max_followers} followers")
                user_id = getters.get_user_id(
                    helper.arguments.server,
                    helper.arguments.user,
                    token,
                    )
                followers = getters.get_new_followers(
                    helper.arguments.server,
                    user_id,
                    helper.arguments.max_followers,
                    all_known_users,
                    )
                add_context.add_user_posts(
                    helper.arguments.server,
                    token,
                    followers,
                    recently_checked_users,
                    all_known_users,
                    seen_urls,
                    )

            if helper.arguments.max_follow_requests > 0:
                logging.info(
f"Getting posts from last {helper.arguments.max_follow_requests} follow requests")
                follow_requests = getters.get_new_follow_requests(
                                    helper.arguments.server,
                                    token,
                                    helper.arguments.max_follow_requests,
                                    all_known_users,
                                    )
                add_context.add_user_posts(
                    helper.arguments.server,
                    token,
                    follow_requests,
                    recently_checked_users,
                    all_known_users,
                    seen_urls,
                    )

            if helper.arguments.from_notifications > 0:
                logging.info(
f"Getting notifications for last {helper.arguments.from_notifications} hours")
                notification_users = getters.get_notification_users(
                                        helper.arguments.server,
                                        token,
                                        all_known_users,
                                        helper.arguments.from_notifications,
                                        )
                add_context.add_user_posts(
                    helper.arguments.server,
                    token,
                    notification_users,
                    recently_checked_users,
                    all_known_users,
                    seen_urls,
                    )

            if helper.arguments.max_bookmarks > 0:
                logging.info(
f"Pulling replies to the last {helper.arguments.max_bookmarks} bookmarks")
                bookmarks = getters.get_bookmarks(
                                helper.arguments.server,
                                token,
                                helper.arguments.max_bookmarks,
                                )
                known_context_urls = getters.get_all_known_context_urls(
                                        helper.arguments.server,
                                        iter(bookmarks),
                                        parsed_urls,
                                        )
                add_context.add_context_urls(
                    helper.arguments.server,
                    token,
                    known_context_urls,
                    seen_urls,
                    )

            if helper.arguments.max_favourites > 0:
                logging.info(
f"Pulling replies to the last {helper.arguments.max_favourites} favourites")
                favourites = getters.get_favourites(
                                helper.arguments.server,
                                token,
                                helper.arguments.max_favourites,
                                )
                known_context_urls = getters.get_all_known_context_urls(
                                        helper.arguments.server,
                                        iter(favourites),
                                        parsed_urls,
                                        )
                add_context.add_context_urls(
                    helper.arguments.server,
                    token,
                    known_context_urls,
                    seen_urls,
                    )

        helper.write_seen_files(
            SEEN_URLS_FILE,
            REPLIED_TOOT_SERVER_IDS_FILE,
            KNOWN_FOLLOWINGS_FILE,
            RECENTLY_CHECKED_USERS_FILE,
            seen_urls,
            replied_toot_server_ids,
            known_followings,
            recently_checked_users,
            )

        Path.unlink(LOCK_FILE)

        if(helper.arguments.on_done):
            try:
                helper.get(f"{helper.arguments.on_done}?rid={run_id}")
            except Exception as ex:
                logging.error(f"Error getting callback url: {ex}")

        logging.info(f"Processing finished in {datetime.now(UTC) - start}.")

    except Exception:
        try: # Try to clean up
            SEEN_URLS_FILE = Path(helper.arguments.state_dir) / "seen_urls"
            REPLIED_TOOT_SERVER_IDS_FILE = Path(
                helper.arguments.state_dir) / "replied_toot_server_ids"
            KNOWN_FOLLOWINGS_FILE = Path(
                helper.arguments.state_dir) / "known_followings"
            RECENTLY_CHECKED_USERS_FILE = Path(
                helper.arguments.state_dir) / "recently_checked_users"
            helper.write_seen_files(
                SEEN_URLS_FILE,
                REPLIED_TOOT_SERVER_IDS_FILE,
                KNOWN_FOLLOWINGS_FILE,
                RECENTLY_CHECKED_USERS_FILE,
                seen_urls,
                replied_toot_server_ids,
                known_followings,
                recently_checked_users,
                )
        except Exception as ex:
            logging.error(f"Error writing seen files: {ex}")
        Path.unlink(LOCK_FILE)
        logging.warning(f"Job failed after {datetime.now(UTC) - start}.")
        if(helper.arguments.on_fail):
            try:
                helper.get(f"{helper.arguments.on_fail}?rid={run_id}")
            except Exception as ex:
                logging.error(f"Error getting callback url: {ex}")
        raise
