"""FediFetcher - a tool to fetch posts from the fediverse."""

import json
import logging
import re
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from dateutil import parser
from psycopg2 import connect

from fedifetcher.api.postgresql.postgresql import PostgreSQLUpdater
from fedifetcher.helpers import cache_manager, helpers
from fedifetcher.helpers.ordered_set import OrderedSet
from fedifetcher.mode import active_users, token_posts, trending_posts


async def main() -> None:  # noqa: PLR0912, C901, PLR0915
    """Run FediFetcher."""
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
    lock_file = helpers.arguments.lock_file

    if( Path(lock_file).exists()):
        logging.info(f"Lock file exists at {lock_file}")

        try:
            with Path(lock_file).open(encoding="utf-8") as file:
                lock_time = parser.parse(file.read())

            if (datetime.now(UTC) - lock_time).total_seconds() >= \
                    helpers.arguments.lock_hours * 60 * 60:
                Path.unlink(lock_file)
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

    with Path(lock_file).open("w", encoding="utf-8") as file:
        file.write(f"{datetime.now(UTC)}")

    replied_toot_server_ids: dict[str, str | None] = {}
    known_followings = OrderedSet([])
    recently_checked_users = OrderedSet({})
    try:
        logging.debug("Loading seen files")
        cache = cache_manager.SeenFilesManager(helpers.arguments.state_dir)
        replied_toot_server_ids, known_followings, recently_checked_users \
                = cache.get_seen_data()

        # Remove any users whose last check is too long in the past from the list
        logging.debug("Removing old users from recently checked users")
        for user in list(recently_checked_users):
            last_check = recently_checked_users.get_time(user)
            user_age = datetime.now(last_check.tzinfo) - last_check
            if(user_age.total_seconds(
            ) > helpers.arguments.remember_users_for_hours * 60 * 60):
                logging.debug(f"Removing user {user} from recently checked users")
                recently_checked_users.remove(user)

        parsed_urls : dict[str, tuple[str | None, str | None]] = {}

        all_known_users = OrderedSet(
            list(known_followings) + list(recently_checked_users))

        if(isinstance(helpers.arguments.access_token, str)):
            helpers.arguments.access_token = [helpers.arguments.access_token]

        admin_token = helpers.arguments.access_token[0]
        external_tokens = helpers.arguments.external_tokens \
            if helpers.arguments.external_tokens else {}
        logging.debug(f"Found {len(helpers.arguments.access_token)} access tokens")
        if external_tokens:
            logging.debug(f"Found {len(external_tokens)} external tokens")
        else:
            logging.warning("No external tokens found")
        conn = connect(
            host="dreamer", \
                # TODO: Make this configurable
            port = 5432,
            database="mastodon_production", \
                # TODO: Make this configurable
            user="teq", \
                # TODO: Make this configurable
            password= \
                helpers.arguments.pgpassword if helpers.arguments.pgpassword else None,
        )
        conn.set_session(autocommit=True)
        pgupdater = PostgreSQLUpdater(conn)
        try:
            logging.info("Getting active user IDs")
            await active_users(replied_toot_server_ids, parsed_urls,
                                admin_token, external_tokens, pgupdater)
        except Exception:
            logging.warning("Error getting active user IDs. This optional feature \
requires the admin:read:accounts scope to be enabled on the first access token \
provided. Continuing without active user IDs.")

        for _token in helpers.arguments.access_token:
            index = helpers.arguments.access_token.index(_token)
            logging.info(f"Getting posts for token {index + 1} of \
{len(helpers.arguments.access_token)}")
            await token_posts(
                _token,
                parsed_urls,
                replied_toot_server_ids,
                all_known_users,
                recently_checked_users,
                known_followings,
                external_tokens,
                pgupdater,
            )

        if external_tokens and helpers.arguments.external_feeds:
            # external_feeds is a comma-separated list of external feeds to fetch
            # from, e.g. "example1.com,example2.com"
            await trending_posts(parsed_urls, admin_token, external_tokens, pgupdater)

        logging.info("Writing seen files")
        cache.write_seen_files(
            replied_toot_server_ids,
            known_followings,
            recently_checked_users,
            )

        Path.unlink(lock_file)

        if(helpers.arguments.on_done):
            try:
                helpers.get(f"{helpers.arguments.on_done}?rid={run_id}")
            except Exception as ex:
                logging.error(f"Error getting callback url: {ex}")

        logging.info(
            f"\033[1m\033[38;5;208mProcessing finished in \
\033[38;5;208m{datetime.now(UTC) - start}.\033[0m")

    except Exception:
        logging.exception("Error running FediFetcher")
        try: # Try to clean up
            parachute_cache = cache_manager.SeenFilesManager(
                helpers.arguments.state_dir)
            parachute_cache.write_seen_files(
                replied_toot_server_ids,
                known_followings,
                recently_checked_users,
                )
            logging.debug("Successfully wrote seen files.")
        except Exception as ex:
            logging.error(f"Error writing seen files: {ex}")
        Path.unlink(lock_file)
        logging.warning(f"Job failed after {datetime.now(UTC) - start}.")
        if(helpers.arguments.on_fail):
            try:
                helpers.get(f"{helpers.arguments.on_fail}?rid={run_id}")
            except Exception as ex:
                logging.error(f"Error getting callback url: {ex}")
        sys.exit(1)
