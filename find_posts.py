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
    helpers,
)
from fedifetcher.find_posts_by_token import find_posts_by_token
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
    try:
        SEEN_URLS_FILE = Path(helpers.arguments.state_dir) / "seen_urls"
        REPLIED_TOOT_SERVER_IDS_FILE = Path(
            helpers.arguments.state_dir) / "replied_toot_server_ids"
        KNOWN_FOLLOWINGS_FILE = Path(helpers.arguments.state_dir) / "known_followings"
        RECENTLY_CHECKED_USERS_FILE = Path(
            helpers.arguments.state_dir) / "recently_checked_users"

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
            ) > helpers.arguments.remember_users_for_hours * 60 * 60):
                recently_checked_users.remove(user)

        parsed_urls : dict[str, tuple[str | None, str | None]] = {}

        all_known_users = OrderedSet(
            list(known_followings) + list(recently_checked_users))

        if(isinstance(helpers.arguments.access_token, str)):
            helpers.arguments.access_token = [helpers.arguments.access_token]

        for _token in helpers.arguments.access_token:
            find_posts_by_token(
                _token,
                seen_urls,
                parsed_urls,
                replied_toot_server_ids,
                all_known_users,
                recently_checked_users,
                known_followings,
            )

        helpers.write_seen_files(
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

        if(helpers.arguments.on_done):
            try:
                helpers.get(f"{helpers.arguments.on_done}?rid={run_id}")
            except Exception as ex:
                logging.error(f"Error getting callback url: {ex}")

        logging.info(f"Processing finished in {datetime.now(UTC) - start}.")

    except Exception:
        try: # Try to clean up
            SEEN_URLS_FILE = Path(helpers.arguments.state_dir) / "seen_urls"
            REPLIED_TOOT_SERVER_IDS_FILE = Path(
                helpers.arguments.state_dir) / "replied_toot_server_ids"
            KNOWN_FOLLOWINGS_FILE = Path(
                helpers.arguments.state_dir) / "known_followings"
            RECENTLY_CHECKED_USERS_FILE = Path(
                helpers.arguments.state_dir) / "recently_checked_users"
            helpers.write_seen_files(
                SEEN_URLS_FILE,
                REPLIED_TOOT_SERVER_IDS_FILE,
                KNOWN_FOLLOWINGS_FILE,
                RECENTLY_CHECKED_USERS_FILE,
                seen_urls,
                replied_toot_server_ids,
                known_followings,
                recently_checked_users,
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
        raise
