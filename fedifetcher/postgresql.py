"""A module for interacting with the PostgreSQL database."""

import logging
from datetime import UTC, datetime

from mastodon.types import Status
from psycopg2 import Error, OperationalError


class PostgreSQLUpdater:
    """A class for updating the PostgreSQL database."""

    def __init__(self, conn) -> None: # noqa: ANN001
        """Initialize the PostgreSQLUpdater."""
        self.conn = conn
        self.updates = []

    def queue_status_update(self,
                    status_id: int, reblogs_count: int, favourites_count: int) -> None:
        """Queue an update to be processed later."""
        if reblogs_count > 0 or favourites_count > 0:
            self.updates.append((status_id, reblogs_count, favourites_count))

    def commit_status_updates(self) -> None:
        """Commit all queued updates to the database."""
        if len(self.updates) == 0:
            return
        try:
            logging.debug(f"Updating {len(self.updates)} status stats")
            with self.conn.cursor() as cursor:
                now = datetime.now(UTC)
                for update in self.updates:
                    logging.debug(
f"Updating {update[0]} to {update[1]} reblogs and {update[2]} favourites")
                    status_id, reblogs_count, favourites_count = update
                    cursor.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM public.status_stats
                            WHERE status_id = %s
                        );
                        """,
                        (status_id,),
                    )
                    exists = cursor.fetchone()[0]
                    if exists:
                        query = """
                UPDATE public.status_stats
                SET reblogs_count = %s, favourites_count = %s, updated_at = %s
                WHERE status_id = %s;
                                """
                        data = (reblogs_count, favourites_count, now, status_id)
                    else:
                        query = """
                INSERT INTO public.status_stats
                (status_id, reblogs_count, favourites_count, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s);
                                """
                        data = (
                            status_id, reblogs_count, favourites_count, now, now)
                    cursor.execute(query, data)
                logging.debug("Committing updates")
                self.conn.commit()
                logging.info(f"Committed {len(self.updates)} updates")
            self.updates = []
        except (OperationalError, Error) as e:
            logging.error(f"Error updating public.status_stats: {e}")

    def cache_status(self, status: Status) -> bool:  # noqa: C901, PLR0915
        """Cache a status in the database.

        We'll be using a table named public.fetched_statuses to store the
        statuses we fetch from the fediverse.

        Parameters
        ----------
        status : Status
            The status to cache.


        Returns
        -------
        bool
            True if the status was newly cached or changed, False otherwise.
        """
        # First, make sure our required fields are present.
        required_attributes = [
            "id",
            "uri",
            "url",
            "created_at",
        ]
        for attribute in required_attributes:
            if not status.get(attribute):
                logging.error(
                    f"Status missing required attribute: {attribute}")
                return False
        # Cast these variables to the correct types.
        status_id_fetched = str(status.get("id"))
        uri = str(status.get("uri"))
        url = str(status.get("url"))
        created_at_original = status.get("created_at")
        edited_at_original = status.get("edited_at")
        replies_count = int(status.get("replies_count"))
        reblogs_count = int(status.get("reblogs_count"))
        favourites_count = int(status.get("favourites_count"))
        # We can determine the originality of the status by comparing the ID in the URL
        # to the ID in the status.
        try:
            logging.debug(f"Caching status {url}")
            original = False
            status_id = None
            status_id_original = None
            if status_id_fetched == url.split("/")[-1]:
                logging.debug(f"Status {url} is original")
                original = True
                status_id_original = status_id_fetched
            else:
                logging.debug(f"Status {url} is not from origin")
            now = datetime.now(UTC)
            query_exists = """
                SELECT *
                FROM public.fetched_statuses
                WHERE uri = %s;
            """
            data = (uri,)
            with self.conn.cursor() as cursor:
                cursor.execute(query_exists, data)
                row = cursor.fetchone()
                if row:  # Check if row exists
                    columns = [column[0] for column in cursor.description]
                    row = dict(zip(columns, row, strict=False))
                if row:
                    try:
                        if not original:
                            if row.get("original"):
                                logging.debug(
                                    f"Already have original status for {uri}, skipping")
                                return False
                            logging.debug("No original status found, caching")
                            got_reblogs_count = row.get("reblogs_count")
                            if got_reblogs_count:
                                reblogs_count = max(reblogs_count, got_reblogs_count)
                            got_favourites_count = row.get("favourites_count")
                            if got_favourites_count:
                                favourites_count = max(
                                    favourites_count, got_favourites_count)
                    except AttributeError:
                        logging.warning(f"Attribute error for {uri}")
                        logging.warning(row)
                        return False
                    # Check public.statuses to see if we already have a local id.
                    query_statuses = """
                    SELECT id
                    FROM public.statuses
                    WHERE uri = %s
                    LIMIT 1;
                    """
                    data = (uri,)
                    cursor.execute(query_statuses, data)
                    result = cursor.fetchone()
                    if result is not None:
                        columns = [column[0] for column in cursor.description]
                        result = dict(zip(columns, result, strict=False))
                        status_id = result.get("id")
                    query = """
                    UPDATE public.fetched_statuses
                    SET text = %s, updated_at = %s, in_reply_to_id_original = %s,
                    reblog_of_id_original = %s, spoiler_text = %s, reply = %s,
                    language = %s, original = %s, poll_id_original = %s,
                    created_at_original = %s, edited_at_original = %s,
                    status_id = %s, status_id_original = %s,
                    replies_count = %s, reblogs_count = %s, favourites_count = %s
                    WHERE uri = %s;
                    """
                    data = (
                        status.get("content"),
                        now,
                        status.get("in_reply_to_id"),
                        status.get("reblog_of_id"),
                        status.get("spoiler_text"),
                        status.get("reply"),
                        status.get("language"),
                        original,
                        status.get("poll").get("id") \
                            if status.get("poll") is not None else None,
                        created_at_original,
                        edited_at_original,
                        status_id,
                        status_id_original,
                        replies_count,
                        reblogs_count,
                        favourites_count,
                        uri,
                    )
                    logging.debug(f"Updating status {url}")
                else:
                    query = """
                    INSERT INTO public.fetched_statuses
                    (uri, text, created_at, updated_at, in_reply_to_id_original,
                    reblog_of_id_original, url, spoiler_text, reply, language,
                    original, poll_id_original,
                    created_at_original, edited_at_original, status_id,
                    status_id_original, replies_count, reblogs_count,
                    favourites_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s);
                    """
                    data = (
                        uri,
                        status.get("content"),
                        now,
                        now,
                        status.get("in_reply_to_id"),
                        status.get("reblog_of_id"),
                        url,
                        status.get("spoiler_text"),
                        status.get("reply"),
                        status.get("language"),
                        original,
                        status.get("poll").get("id") \
                            if status.get("poll") is not None else None,
                        created_at_original,
                        edited_at_original,
                        status_id,
                        status_id_original,
                        replies_count,
                        reblogs_count,
                        favourites_count,
                    )
                    logging.debug(f"Inserting status {url}")
                cursor.execute(query, data)
                self.conn.commit()
                logging.debug(f"Status {url} cached")
                return True
        except (OperationalError, Error) as e:
            logging.error(f"Error caching status: {e}")
        return False

    def get_from_cache(self, url: str) -> Status | None:
        """Get a status from the cache.

        Parameters
        ----------
        url : str
            The URL of the status.

        Returns
        -------
        Status | None
            The status if found, None otherwise.
        """
        try:
            # Lookup the status in the cache.
            query = """
            SELECT *
            FROM public.fetched_statuses
            WHERE url = %s
            LIMIT 1;
            """
            data = (url,)
            with self.conn.cursor() as cursor:
                cursor.execute(query, data)
                result = cursor.fetchone()
                if result is not None:
                    columns = [column[0] for column in cursor.description]
                    result = dict(zip(columns, result, strict=False))
                    logging.info(f"Got status from cache: {url}")
                    return Status(
                        id=result.get("status_id"),
                        uri=result.get("uri"),
                        url=result.get("url"),
                        created_at=result.get("created_at_original"),
                        edited_at=result.get("edited_at_original"),
                        replies_count=result.get("replies_count"),
                        reblogs_count=result.get("reblogs_count"),
                        favourites_count=result.get("favourites_count"),
                        content=result.get("text"),
                        in_reply_to_id=result.get("in_reply_to_id_original"),
                        reblog_of_id=result.get("reblog_of_id_original"),
                        spoiler_text=result.get("spoiler_text"),
                        reply=result.get("reply"),
                        language=result.get("language"),
                        in_reply_to_account_id=result.get("in_reply_to_account_id_original"),
                        poll_id=result.get("poll_id_original"),
                        account_id=result.get("account_id"),
                    )
        except (OperationalError, Error) as e:
            logging.error(f"Error getting status from cache: {e}")
        return None
