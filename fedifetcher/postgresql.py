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

    def cache_status(self, status: Status) -> bool:
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
            "edited_at",
            "replies_count",
            "reblogs_count",
            "favourites_count",
        ]
        for attribute in required_attributes:
            if not hasattr(status, attribute):
                logging.error(
                    f"Status missing required attribute: {attribute}")
                return False
        # Cast these variables to the correct types.
        status_id_fetched = int(status.id)
        uri = str(status.uri)
        url = str(status.url)
        created_at_original = status.created_at
        edited_at_original = status.edited_at
        replies_count = int(status.replies_count)
        reblogs_count = int(status.reblogs_count)
        favourites_count = int(status.favourites_count)
        # We can determine the originality of the status by comparing the ID in the URL
        # to the ID in the status.
        try:
            logging.debug(f"Caching status {status.id}")
            original = False
            status_id = None
            status_id_original = None
            if status_id_fetched == int(url.split("/")[-1]):
                original = True
                status_id_original = status_id_fetched
            now = datetime.now(UTC)
            query = """
            SELECT EXISTS (
                SELECT 1
                FROM public.fetched_statuses
                WHERE uri = %s
            );
            """
            data = (uri,)
            with self.conn.cursor() as cursor:
                cursor.execute(query, data)
                exists = cursor.fetchone()[0]
                if exists:
                    if not original:
                        if exists["original"]:
                            logging.debug(
                                f"Already have original status for {uri}, skipping")
                            return False
                        reblogs_count = max(reblogs_count, exists["reblogs_count"])
                        favourites_count = (
                            favourites_count + exists["favourites_count"])
                    # Check public.statuses to see if we already have a local id.
                    query = """
                    SELECT id
                    FROM public.statuses
                    WHERE uri = %s
                    LIMIT 1;
                    """
                    data = (uri,)
                    cursor.execute(query, data)
                    result = cursor.fetchone()
                    if result is not None:
                        status_id = result["id"]
                    query = """
                    UPDATE public.fetched_statuses
                    SET text = %s, updated_at = %s, in_reply_to_id_original = %s,
                    reblog_of_id_original = %s, spoiler_text = %s, reply = %s,
                    language = %s, original = %s, account_id = %s,
                    in_reply_to_account_id_original = %s, poll_id_original = %s,
                    created_at_original = %s, edited_at_original = %s,
                    status_id = %s, status_id_original = %s,
                    replies_count = %s, reblogs_count = %s, favourites_count = %s
                    WHERE uri = %s;
                    """
                    data = (
                        status.content,
                        now,
                        status.in_reply_to_id,
                        status.reblog_of_id,
                        status.spoiler_text,
                        status.reply,
                        status.language,
                        original,
                        status.account.id,
                        status.in_reply_to_account_id_original,
                        status.poll.id if status.poll is not None else None,
                        created_at_original,
                        edited_at_original,
                        status_id,
                        status_id_original,
                        replies_count,
                        reblogs_count,
                        favourites_count,
                        uri,
                    )
                else:
                    query = """
                    INSERT INTO public.fetched_statuses
                    (uri, text, created_at, updated_at, in_reply_to_id_original,
                    reblog_of_id_original, url, spoiler_text, reply, language,
                    conversation_id, original, account_id, application_id,
                    in_reply_to_account_id_original, poll_id_original,
                    created_at_original, edited_at_original, status_id,
                    status_id_original, replies_count, reblogs_count,
                    favourites_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, Null, %s, %s,
                    Null, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    data = (
                        uri,
                        status.content,
                        now,
                        now,
                        status.in_reply_to_id,
                        status.reblog_of_id,
                        url,
                        status.spoiler_text,
                        status.reply,
                        status.language,
                        original,
                        status.account.id,
                        status.in_reply_to_account_id_original,
                        status.poll.id if status.poll is not None else None,
                        created_at_original,
                        edited_at_original,
                        status_id,
                        status_id_original,
                        replies_count,
                        reblogs_count,
                        favourites_count,
                    )
                cursor.execute(query, data)
                self.conn.commit()
                logging.debug(f"Status {status.id} cached")
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
                    return Status(
                        id=result["status_id"],
                        uri=result["uri"],
                        url=result["url"],
                        created_at=result["created_at_original"],
                        edited_at=result["edited_at_original"],
                        replies_count=result["replies_count"],
                        reblogs_count=result["reblogs_count"],
                        favourites_count=result["favourites_count"],
                        content=result["text"],
                        in_reply_to_id=result["in_reply_to_id_original"],
                        reblog_of_id=result["reblog_of_id_original"],
                        spoiler_text=result["spoiler_text"],
                        reply=result["reply"],
                        language=result["language"],
                        in_reply_to_account_id=result["in_reply_to_account_id_original"],
                        poll_id=result["poll_id_original"],
                        account_id=result["account_id"],
                    )
        except (OperationalError, Error) as e:
            logging.error(f"Error getting status from cache: {e}")
        return None
