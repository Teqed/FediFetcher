"""Mastodon API functions."""
import logging
from collections.abc import Generator, Iterator
from datetime import UTC, datetime, timedelta

import requests
from mastodon import (
    Mastodon,
    MastodonAPIError,
    MastodonError,
    MastodonNotFoundError,
    MastodonRatelimitError,
    MastodonUnauthorizedError,
)

from . import helpers


def mastodon(server: str, token: str | None = None) -> Mastodon:
    """Get a Mastodon instance."""
    if not hasattr(mastodon, "sessions"):
        mastodon.sessions = {}

    if server not in mastodon.sessions:
        logging.warning(f"Creating Mastodon session for {server}")
        session = requests.Session()
        session.headers.update({
            "User-Agent": "FediFetcher (https://go.thms.uk/mgr)",
        })
        mastodon.sessions[server] = Mastodon(
            access_token=token if token else None,
            api_base_url=server if server else helpers.arguments.server,
            session=session,
            debug_requests=False,
            ratelimit_method="wait",
            ratelimit_pacefactor=1.1,
            request_timeout=300,
        )
    return mastodon.sessions[server]

def get_user_id(
        user : str,
        server: str,
        token : str | None = None,
        ) -> str | None:
    """Get the user id from the server using a username.

    This function retrieves the user id from the server by \
        performing a search based on the provided username.

    Args:
    ----
    server (str): The server to get the user id from.
    token (str): The access token to use for the request.
    user (str): The username for which to retrieve the user id.

    Returns:
    -------
    str | None: The user id if found, or None if the user is not found.
    """
    try:
        if server == helpers.arguments.server or not server:
            return mastodon(server,token).account_search(
                q = user,
                limit = 1,
                following = False,
                resolve = True,
            )[0][id]
        return mastodon(server=server).account_search(
            q = user,
            limit = 1,
        )[0][id]
    except MastodonNotFoundError :
        logging.error(
f"Error getting ID for user {user}. Status code: 404. \
User not found.")
    except MastodonUnauthorizedError:
        if token:
            logging.error(
f"Error getting ID for user {user}. Status code: 401. \
Ensure your access token is correct.")
        else:
            logging.error(
f"Error getting ID for user {user}. Status code: 401. \
This server requires authentication.")
    except MastodonError:
        logging.exception(
f"Error getting ID for user {user}")
        return None

def get_timeline(
    server: str,
    token: str | None = None,
    timeline: str = "local",
    limit: int = 40,
) -> Iterator[dict]:
    """Get all posts in the user's home timeline.

    Args:
    ----
    timeline (str): The timeline to get.
    token (str): The access token to use for the request.
    server (str): The server to get the timeline from.
    limit (int): The maximum number of posts to get.

    Yields:
    ------
    dict: A post from the timeline.

    Raises:
    ------
    Exception: If the access token is invalid.
    Exception: If the access token does not have the correct scope.
    Exception: If the server returns an unexpected status code.
    """
    try:
        toots: list[dict] = mastodon(server, token).timeline(
            timeline=timeline, limit=limit)
        number_of_toots_received = len(toots)
        yield from toots
        while number_of_toots_received < limit and toots[-1].get("_pagination_next"):
            more_toots = mastodon(server, token).fetch_next(toots)
            if not more_toots:
                break
            number_of_toots_received += len(more_toots)
            yield from more_toots
    except MastodonRatelimitError:
        logging.error(
"Error getting timeline. Status code: 429. \
You are being rate limited. Try again later.")
        return None
    except MastodonUnauthorizedError:
        logging.error(
"Error getting timeline. Status code: 401. \
Ensure your access token is correct")
        return None
    except MastodonAPIError:
        logging.exception(
"Error getting timeline. \
Make sure you have the read:statuses scope enabled for your access token.")
        return None
    except MastodonError:
        logging.exception("Error getting timeline.")
        return None
    except Exception:
        logging.exception("Error getting timeline.")
        raise

    logging.info(f"Found {number_of_toots_received} toots in timeline")

def get_active_user_ids(
        server : str,
        access_token : str,
        reply_interval_hours : int,
        ) -> Generator[str, None, None]:
    """Get all user IDs on the server that have posted in the given time interval.

    Args:
    ----
    server (str): The server to get the user IDs from.
    access_token (str): The access token to use for authentication.
    reply_interval_hours (int): The number of hours to look back for activity.


    Returns:
    -------
    Generator[str, None, None]: A generator of user IDs.


    Raises:
    ------
    Exception: If the access token is invalid.
    Exception: If the access token does not have the correct scope.
    Exception: If the server returns an unexpected status code.
    """
    logging.debug(f"Getting active user IDs for {server}")
    logging.debug(f"Reply interval: {reply_interval_hours} hours")
    since = datetime.now(UTC) - timedelta(days=reply_interval_hours / 24 + 1)
    logging.debug(f"Since: {since}")
    local_accounts = mastodon(server, access_token).admin_accounts_v2(
        origin="local",
        status="active",
        )
    logging.debug(f"Found {len(local_accounts)} accounts")
    if local_accounts:
        try:
            logging.debug(
f"Getting user IDs for {len(local_accounts)} local accounts")
            for user in local_accounts:
                logging.debug(f"User: {user.username}")
                last_status_at = user["account"]["last_status_at"]
                logging.debug(f"Last status at: {last_status_at}")
                if last_status_at:
                    last_active = last_status_at.astimezone(UTC)
                    logging.debug(f"Last active: {last_active}")
                    if last_active > since:
                        logging.info(f"Found active user: {user['username']}")
                        yield user["id"]
        except MastodonRatelimitError:
            logging.error(
"Error getting timeline. Status code: 429. \
You are being rate limited. Try again later.")
            return None
        except MastodonUnauthorizedError:
            logging.error(
"Error getting user IDs. Status code: 401. \
Ensure your access token is correct.")
            return None
        except MastodonAPIError:
            logging.exception(
"Error getting user IDs. \
Make sure you have the read:statuses scope enabled for your access token.")
            return None
        except MastodonError:
            logging.exception("Error getting user IDs.")
            return None
        except Exception:
            logging.exception("Error getting user IDs.")
            raise

def get_me(server : str, token : str) -> str | None:
    """Get the user ID of the authenticated user.

    Args:
    ----
    token (str): The access token to use for authentication.
    server (str): The server to get the user ID from. Defaults to the server \
        specified in the arguments.

    Returns:
    -------
    str: The user ID of the authenticated user.

    Raises:
    ------
    Exception: If the access token is invalid.
    Exception: If the access token does not have the correct scope.
    Exception: If the server returns an unexpected status code.
    """
    try:
        return mastodon(server, token).account_verify_credentials()["id"]
    except MastodonRatelimitError:
        logging.error(
"Error getting timeline. Status code: 429. \
You are being rate limited. Try again later.")
        return None
    except MastodonUnauthorizedError:
        logging.error(
"Error getting user IDs. Status code: 401. \
Ensure your access token is correct.")
        return None
    except MastodonAPIError:
        logging.exception(
"Error getting user IDs. \
Make sure you have the read:statuses scope enabled for your access token.")
        return None
    except MastodonError:
        logging.exception("Error getting user IDs.")
        return None
    except Exception:
        logging.exception("Error getting user IDs.")
        raise
