"""A module for interacting with the PostgreSQL database."""

import json
import logging
from mastodon import favourites

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
                for update in self.updates:
                    logging.debug(
f"Updating {update[0]} to {update[1]} reblogs and {update[2]} favourites")
                    status_id, reblogs_count, favourites_count = update
                    # Convert the favourites into reactions.
                    # Reactions are a JSON, and we'll want to set the count of the
                    # star reaction to the number of favourites.
                    # For example: {"⭐": 0}
                    reactions = json.dumps({"⭐": favourites_count})
                    score = reblogs_count + favourites_count
                    cursor.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM public.note
                            WHERE id = %s
                        );
                        """,
                        (status_id,),
                    )
                    exists = cursor.fetchone()[0]
                    if exists:
                        query = """
                UPDATE public.note
                SET "renoteCount" = %s, reactions = %s, score = %s
                WHERE id = %s;
                                """
                        data = (reblogs_count, reactions, score, status_id)
                        cursor.execute(query, data) # see below
                    else:
                        logging.warning(
                            f"Status {status_id} not found in public.note")
                logging.debug("Committing updates")
                self.conn.commit()
                logging.info(f"Committed {len(self.updates)} updates")
            self.updates = []
        except (OperationalError, Error) as e:
            logging.error(f"Error updating public.note: {e}")

    def cache_status(self, status: Status) -> bool:
        """Cache a status in the database.

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
        if status is None:
            logging.error("Status is None")
            return False
        required_attributes = [
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
        uri = str(status.get("uri"))
        url = str(status.get("url"))
        replies_count = int(status.get("replies_count"))
        reblogs_count = int(status.get("reblogs_count"))
        favourites_count = int(status.get("favourites_count"))
        # We can determine the originality of the status by comparing the ID in the URL
        # to the ID in the status.
        try:
            query_exists = """
                SELECT *
                FROM public.note
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
                        got_reblogs_count = row.get("renoteCount")
                        if got_reblogs_count:
                            reblogs_count = max(reblogs_count, got_reblogs_count)
                        got_favourites_count = row.get("reactions").get("⭐")
                        if got_favourites_count:
                            favourites_count = max(
                                favourites_count, got_favourites_count)
                    except AttributeError:
                        logging.warning(f"Attribute error for {uri}")
                        logging.warning(row)
                        return False
                    query = """
                    UPDATE public.note
                    SET "repliesCount" = %s,
                    "renoteCount" = %s,
                    score = %s,
                    reactions = %s
                    WHERE uri = %s;
                    """
                    reactions = json.dumps({"⭐": favourites_count})
                    data = (
                        replies_count,
                        reblogs_count,
                        (reblogs_count + favourites_count),
                        reactions,
                        uri,
                    )
                    logging.info(f"Updating status {url}")
                    cursor.execute(query, data)
                else:
                    logging.warning(f"Status {url} not found in public.note")
                self.conn.commit()
                return True
        except (OperationalError, Error) as e:
            logging.error(f"Error caching status: {e}")
        return False

    def query_public_statuses(self, uri: str, conn) -> int | None:  # noqa: ANN001
        """Query public.note for a status ID."""
        query_statuses = """
                    SELECT id
                    FROM public.note
                    WHERE uri = %s
                    LIMIT 1;
                    """
        data = (uri,)
        with conn.cursor() as cursor:
            cursor.execute(query_statuses, data)
            result = cursor.fetchone()
            if result is not None:
                columns = [column[0] for column in cursor.description]
                result = dict(zip(columns, result, strict=False))
                return result.get("id")
            return None

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
            FROM public.note
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
                    logging.info(f"Got status from cache: {url} \
, ID: {result.get('id')}")
                    status_id = result.get("id")
                    favourites_count = 0
                    reactions = result.get("reactions")
                    if reactions:
                        for reaction in reactions:
                            favourites_count += reactions.get(reaction)
                    status = Status(
                        id=status_id,
                        uri=result.get("uri"),
                        url=result.get("url"),
                        created_at=result.get("createdAt"),
                        edited_at=result.get("updatedAt"),
                        replies_count=result.get("repliesCount"),
                        reblogs_count=result.get("renoteCount"),
                        favourites_count=favourites_count,
                        content=result.get("text"),
                        in_reply_to_id=result.get("replyid"),
                        reblog_of_id=result.get("renoteid"),
                        spoiler_text=result.get("cw"),
                        reply=bool(result.get("replyid")),
                        in_reply_to_account_id=result.get("replyuserid"),
                        account_id=result.get("userId"),
                    )
                    if not status_id:
                        logging.warning(
                            f"Status {url} not found in public.note")
                    return status
        except (OperationalError, Error) as e:
            logging.error(f"Error getting status from cache: {e}")
        logging.debug(f"Status not found in cache: {url}")
        return None

    def get_dict_from_cache(
            self, urls: list[str]) -> dict[str, Status | None]:
        """Get a list of statuses from the cache.

        Parameters
        ----------
        urls : list[str]
            The URLs of the statuses.

        Returns
        -------
        list[Status | None]
            The statuses if found, None otherwise.
        """
        # This will take a list and make a single query to the database.
        # This is much faster than querying the database for each status.
        try:
            # Lookup the statuses in the cache.
            query = """
            SELECT *
            FROM public.note
            WHERE url = ANY(%s);
            """
            data = (urls,)
            with self.conn.cursor() as cursor:
                cursor.execute(query, data)
                results = cursor.fetchall().copy()
                columns = [column[0] for column in cursor.description]
                if results is not None:
                    statuses = {}
                    for result in results:
                        status_dict = dict(zip(columns, result, strict=False))
                        url = status_dict.get("url")
                        if not url:
                            logging.warning(f"Problem with {status_dict}")
                            logging.debug(result)
                            continue
                        # Count the total number of reactions.
                        # Return that number as the favourites_count.
                        favourites_count = 0
                        reactions = status_dict.get("reactions")
                        if reactions:
                            for reaction in reactions:
                                favourites_count += reactions.get(reaction)
                        status = Status(
                            id=status_dict.get("id"),
                            uri=status_dict.get("uri"),
                            url=url,
                            created_at=status_dict.get("createdAt"),
                            edited_at=status_dict.get("updatedAt"),
                            replies_count=status_dict.get("repliesCount"),
                            reblogs_count=status_dict.get("renoteCount"),
                            favourites_count=favourites_count,
                            content=status_dict.get("text"),
                            in_reply_to_id=status_dict.get("replyId"),
                            reblog_of_id=status_dict.get("renoteId"),
                            spoiler_text=status_dict.get("cw"),
                            reply=bool(status_dict.get("replyId")),
                            in_reply_to_account_id=status_dict.get("replyUserId"),
                            account_id=status_dict.get("userId"),
                        )
                        statuses[url] = status
                    return statuses
        except (OperationalError, Error) as e:
            logging.error(f"Error getting statuses from cache: {e}")
        logging.debug(f"Statuses not found in cache: {urls}")
        return {}
