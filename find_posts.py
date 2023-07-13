#!/usr/bin/env python3
"""FediFetcher - a tool to fetch posts from the fediverse."""

import json
import logging
import re
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from dateutil import parser

from fedifetcher import (
    add_context,
    api_mastodon,
    getter_wrappers,
    helpers,
)
from fedifetcher.find_posts_by_token import find_posts_by_token
from fedifetcher.find_trending_posts import find_trending_posts
from fedifetcher.ordered_set import OrderedSet

if __name__ == "__main__":
    start = datetime.now(UTC)

    if(helpers.arguments.config):
        if Path(helpers.arguments.config).exists():
            with Path(helpers.arguments.config).open(encoding="utf-8") as file:
                config = json.load(file)

            for key in config:
                setattr(helpers.arguments, key.lower().replace("-","_"), config[key])

        else:
            logging.critical(f"Config file {helpers.arguments.config} doesn't exist")
            sys.exit(1)

    if(helpers.arguments.server is None or helpers.arguments.access_token is None):
        logging.critical("You must supply at least a server name and an access token")
        sys.exit(1)

    # in case someone provided the server name as url instead,
    helpers.arguments.server = re.sub(
        "^(https://)?([^/]*)/?$", "\\2", helpers.arguments.server)

    helpers.setup_logging()

    logging.info("Starting FediFetcher")

    run_id = uuid.uuid4()

    if(helpers.arguments.on_start):
        try:
            helpers.get(f"{helpers.arguments.on_start}?rid={run_id}")
        except Exception as ex:
            logging.error(f"Error getting callback url: {ex}")

    if helpers.arguments.lock_file is None:
        helpers.arguments.lock_file = Path(helpers.arguments.state_dir) / "lock.lock"
    LOCK_FILE = helpers.arguments.lock_file

    if( Path(LOCK_FILE).exists()):
        logging.info(f"Lock file exists at {LOCK_FILE}")

        try:
            with Path(LOCK_FILE).open(encoding="utf-8") as file:
                lock_time = parser.parse(file.read())

            if (datetime.now(UTC) - lock_time).total_seconds() >= \
                    helpers.arguments.lock_hours * 60 * 60:
                Path.unlink(LOCK_FILE)
                logging.info("Lock file has expired. Removed lock file.")
            else:
                logging.info(f"Lock file age is {datetime.now(UTC) - lock_time} - \
below --lock-hours={helpers.arguments.lock_hours} provided.")
                if(helpers.arguments.on_fail):
                    try:
                        helpers.get(f"{helpers.arguments.on_fail}?rid={run_id}")
                    except Exception as ex:
                        logging.error(f"Error getting callback url: {ex}")
                sys.exit(1)

        except Exception:
            logging.warning("Cannot read logfile age - aborting.")
            if(helpers.arguments.on_fail):
                try:
                    helpers.get(f"{helpers.arguments.on_fail}?rid={run_id}")
                except Exception as ex:
                    logging.error(f"Error getting callback url: {ex}")
            sys.exit(1)

    with Path(LOCK_FILE).open("w", encoding="utf-8") as file:
        file.write(f"{datetime.now(UTC)}")

    seen_urls = OrderedSet()
    replied_toot_server_ids: dict[str, str | None] = {}
    known_followings = OrderedSet([])
    recently_checked_users = OrderedSet({})
    status_id_cache: dict[str, str] = {}
    try:
        logging.info("Loading seen files")
        SEEN_URLS_FILE = Path(helpers.arguments.state_dir) / "seen_urls"
        REPLIED_TOOT_SERVER_IDS_FILE = Path(
            helpers.arguments.state_dir) / "replied_toot_server_ids"
        KNOWN_FOLLOWINGS_FILE = Path(helpers.arguments.state_dir) / "known_followings"
        RECENTLY_CHECKED_USERS_FILE = Path(
            helpers.arguments.state_dir) / "recently_checked_users"
        STATUS_ID_CACHE_FILE = Path(helpers.arguments.state_dir) / "status_id_cache"

        if Path(SEEN_URLS_FILE).exists():
            with Path(SEEN_URLS_FILE).open(encoding="utf-8") as file:
                seen_urls = OrderedSet(file.read().splitlines())
                logging.info(f"Loaded {len(seen_urls)} seen URLs")

        if Path(REPLIED_TOOT_SERVER_IDS_FILE).exists():
            with Path(REPLIED_TOOT_SERVER_IDS_FILE).open(encoding="utf-8") as file:
                replied_toot_server_ids = json.load(file)
                logging.info(f"Loaded {len(replied_toot_server_ids)} replied toot IDs")

        if Path(KNOWN_FOLLOWINGS_FILE).exists():
            with Path(KNOWN_FOLLOWINGS_FILE).open(encoding="utf-8") as file:
                known_followings = OrderedSet(file.read().splitlines())
                logging.info(f"Loaded {len(known_followings)} known followings")

        if Path(RECENTLY_CHECKED_USERS_FILE).exists():
            with Path(RECENTLY_CHECKED_USERS_FILE).open(encoding="utf-8") as file:
                recently_checked_users = OrderedSet(list(json.load(file)))
                logging.info(
                    f"Loaded {len(recently_checked_users)} recently checked users")

        if Path(STATUS_ID_CACHE_FILE).exists():
            with Path(STATUS_ID_CACHE_FILE).open(encoding="utf-8") as file:
                status_id_cache = json.load(file)
                logging.info(f"Loaded {len(status_id_cache)} status IDs")

        # Remove any users whose last check is too long in the past from the list
        logging.info("Removing old users from recently checked users")
        for user in list(recently_checked_users):
            last_check = recently_checked_users.get_time(user)
            user_age = datetime.now(last_check.tzinfo) - last_check
            if(user_age.total_seconds(
            ) > helpers.arguments.remember_users_for_hours * 60 * 60):
                logging.info(f"Removing user {user} from recently checked users")
                recently_checked_users.remove(user)

        parsed_urls : dict[str, tuple[str | None, str | None]] = {}

        all_known_users = OrderedSet(
            list(known_followings) + list(recently_checked_users))

        if(isinstance(helpers.arguments.access_token, str)):
            helpers.arguments.access_token = [helpers.arguments.access_token]

        admin_token = helpers.arguments.access_token[0]
        external_tokens = helpers.arguments.external_tokens \
            if helpers.arguments.external_tokens else None
        logging.warning(f"Found {len(helpers.arguments.access_token)} access tokens")
        if external_tokens:
            logging.warning(f"Found {len(external_tokens)} external tokens")
        else:
            logging.warning("No external tokens found")
        try:
            logging.info("Getting active user IDs")
            user_ids = list(api_mastodon.get_active_user_ids(
                helpers.arguments.server,
                admin_token,
                helpers.arguments.reply_interval_in_hours,
                ))
            logging.debug(f"Found user IDs: {user_ids}")
            """pull the context toots of toots user replied to, from their
            original server, and add them to the local server."""
            logging.info("Pulling context toots for replies")
            logging.debug("Found user ID, getting reply toots")
            reply_toots = getter_wrappers.get_all_reply_toots(
                helpers.arguments.server,
                user_ids,
                admin_token,
                seen_urls,
                helpers.arguments.reply_interval_in_hours,
            )
            logging.debug("Found reply toots, getting known context URLs")
            known_context_urls = getter_wrappers.get_all_known_context_urls(
                helpers.arguments.server,
                reply_toots,
                parsed_urls,
                )
            logging.debug("Found known context URLs, getting replied toot IDs")
            seen_urls.update(known_context_urls)
            replied_toot_ids = getter_wrappers.get_all_replied_toot_server_ids(
                helpers.arguments.server,
                reply_toots,
                replied_toot_server_ids,
                parsed_urls,
            )
            logging.debug("Found replied toot IDs, getting context URLs")
            context_urls = getter_wrappers.get_all_context_urls(
                helpers.arguments.server,
                replied_toot_ids,
                )
            logging.debug("Found context URLs, adding context URLs")
            add_context.add_context_urls(
                helpers.arguments.server,
                admin_token,
                context_urls,
                seen_urls,
                )
            logging.debug("Added context URLs")
        except Exception:
            logging.warning("Error getting active user IDs. This optional feature \
requires the admin:read:accounts scope to be enabled on the first access token \
provided. Continuing without active user IDs.")

        for _token in helpers.arguments.access_token:
            logging.info("Getting posts for token")
            find_posts_by_token(
                _token,
                seen_urls,
                parsed_urls,
                replied_toot_server_ids,
                all_known_users,
                recently_checked_users,
                known_followings,
                external_tokens,
            )

        if external_tokens and helpers.arguments.pgpassword \
                and helpers.arguments.external_feeds:
            # external_feeds is a comma-separated list of external feeds to fetch
            # from, e.g. "example1.com,example2.com"
            external_feeds = helpers.arguments.external_feeds.split(",")
            logging.info("Getting trending posts")
            trending_posts = find_trending_posts(
                helpers.arguments.server,
                admin_token,
                external_feeds,
                external_tokens,
                helpers.arguments.pgpassword,
                status_id_cache,
            )
            logging.info(
f"Found {len(trending_posts)} trending posts, getting known context URLs")
            trending_posts = [
                post for post in trending_posts
                if post["replies_count"] != 0 or post["in_reply_to_id"] is not None
            ]
            logging.info(
f"Found {len(trending_posts)} trending posts with replies, getting known \
context URLs")
            known_context_urls = getter_wrappers.get_all_known_context_urls(
                helpers.arguments.server,
                trending_posts,
                parsed_urls,
                )
            logging.info("Found known context URLs, getting context URLs")
            add_context.add_context_urls(
                helpers.arguments.server,
                admin_token,
                known_context_urls,
                seen_urls,
                )
            logging.info("Added context URLs")

        logging.info("Writing seen files")
        helpers.write_seen_files(
            SEEN_URLS_FILE,
            REPLIED_TOOT_SERVER_IDS_FILE,
            KNOWN_FOLLOWINGS_FILE,
            RECENTLY_CHECKED_USERS_FILE,
            STATUS_ID_CACHE_FILE,
            seen_urls,
            replied_toot_server_ids,
            known_followings,
            recently_checked_users,
            status_id_cache,
            )

        Path.unlink(LOCK_FILE)

        if(helpers.arguments.on_done):
            try:
                helpers.get(f"{helpers.arguments.on_done}?rid={run_id}")
            except Exception as ex:
                logging.error(f"Error getting callback url: {ex}")

        logging.info(f"Processing finished in {datetime.now(UTC) - start}.")

    except Exception:
        logging.exception("Error running FediFetcher")
        try: # Try to clean up
            SEEN_URLS_FILE = Path(helpers.arguments.state_dir) / "seen_urls"
            REPLIED_TOOT_SERVER_IDS_FILE = Path(
                helpers.arguments.state_dir) / "replied_toot_server_ids"
            KNOWN_FOLLOWINGS_FILE = Path(
                helpers.arguments.state_dir) / "known_followings"
            RECENTLY_CHECKED_USERS_FILE = Path(
                helpers.arguments.state_dir) / "recently_checked_users"
            STATUS_ID_CACHE_FILE = Path(
                helpers.arguments.state_dir) / "status_id_cache"
            helpers.write_seen_files(
                SEEN_URLS_FILE,
                REPLIED_TOOT_SERVER_IDS_FILE,
                KNOWN_FOLLOWINGS_FILE,
                RECENTLY_CHECKED_USERS_FILE,
                STATUS_ID_CACHE_FILE,
                seen_urls,
                replied_toot_server_ids,
                known_followings,
                recently_checked_users,
                status_id_cache,
                )
            logging.info("Successfully wrote seen files.")
        except Exception as ex:
            logging.error(f"Error writing seen files: {ex}")
        Path.unlink(LOCK_FILE)
        logging.warning(f"Job failed after {datetime.now(UTC) - start}.")
        if(helpers.arguments.on_fail):
            try:
                helpers.get(f"{helpers.arguments.on_fail}?rid={run_id}")
            except Exception as ex:
                logging.error(f"Error getting callback url: {ex}")
        sys.exit(1)
