"""A module for interacting with the PostgreSQL database."""

import logging
from datetime import UTC, datetime

from psycopg2 import Error, OperationalError


class PostgreSQLUpdater:
    """A class for updating the PostgreSQL database."""

    def __init__(self, conn) -> None: # noqa: ANN101, ANN001
        """Initialize the PostgreSQLUpdater."""
        self.conn = conn
        self.updates = []

    def queue_update(self, # noqa: ANN101
                    status_id: int, reblogs_count: int, favourites_count: int) -> None:
        """Queue an update to be processed later."""
        self.updates.append((status_id, reblogs_count, favourites_count))

    def commit_updates(self) -> None: # noqa: ANN101
        """Commit all queued updates to the database."""
        if len(self.updates) == 0:
            return
        try:
            logging.info(f"Updating {len(self.updates)} status stats")
            with self.conn.cursor() as cursor:
                now = datetime.now(UTC)
                for update in self.updates:
                    logging.info(
f"Updating status stats for {update[0]} to {update[1]} \
reblogs and {update[2]} favourites")
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
                logging.info("Committing updates")
                self.conn.commit()
                logging.info(f"Committed {len(self.updates)} updates")
            self.updates = []
        except (OperationalError, Error) as e:
            logging.error(f"Error updating public.status_stats: {e}")
