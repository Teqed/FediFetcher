"""Pull trending posts from a list of Mastodon servers, using tokens."""


import logging
from datetime import UTC, datetime

import psycopg2

from fedifetcher import api_mastodon


def pgupdate(
        conn,
        status_id: int,
        reblogs_count: int,
        favourites_count: int,
) -> None:
    """Update the public.status_stats table with the trending posts."""
    # First, check if the status_id is already in the table.
    # If it is, update the existing row with the new data.
    # If it isn't, insert a new row.
    cursor = conn.cursor()
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
    cursor_fetchone = cursor.fetchone()
    if cursor_fetchone:
        exists = cursor_fetchone[0]
        now = datetime.now(UTC)
        if exists:
            cursor.execute(
                """
                UPDATE public.status_stats
                SET reblogs_count = %s, favourites_count = %s, updated_at = %s
                WHERE status_id = %s;
                """,
                (reblogs_count, favourites_count, now, status_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO public.status_stats
                (status_id, reblogs_count, favourites_count, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (status_id, reblogs_count, favourites_count, now, now),
            )
    conn.commit()
    cursor.close()

def find_trending_posts(
        home_server: str,
        home_token: str,
        external_tokens: dict[str, str],
        pgpassword: str,
        ) -> list[dict[str, str]]:
    """Pull trending posts from a list of Mastodon servers, using tokens."""
    logging.debug("Finding trending posts")
    conn = psycopg2.connect(
    host="dreamer",
    port = 5432,
    database="mastodon_production",
    user="teq",
    password=pgpassword,
    )

    # For each key in external_tokens, query its mastodon API for trending posts.
    # Later, we're going to compare these results to each other.
    all_trending_posts = []
    for key in external_tokens:
        logging.info(f"Finding trending posts on {key}")
        trending_posts = api_mastodon.get_trending_posts(key, external_tokens[key])
        # A trending post might have already appeared from another server.
        # So, if the "url" of a trending post is already in the list, don't add it,
        # instead, add its 'reblogs_count' to the existing post's 'reblogs_count',
        # and its 'favourites_count' to the existing post's 'favourites_count'.
        for post in trending_posts:
            if post["url"] in [post["url"] for post in all_trending_posts]:
                for existing_post in all_trending_posts:
                    if existing_post["url"] == post["url"]:
                        existing_post["reblogs_count"] += post["reblogs_count"]
                        existing_post["favourites_count"] += post["favourites_count"]
            else:
                logging.info(f"Adding {post['url']} to trending posts")
                all_trending_posts.append(post)

    # We're going to updaet the public.status_stats table with the trending posts.
    # We'll navigate by status_id, which we'll need to fetch from our home server,
    # since it's different from the status's home server's ID for it.
    # We can do a lookup on Mastodon API using the URL of the status.
    # We'll add this as a property to each trending post, named 'local_status_id'.
    for post in all_trending_posts:
        post["local_status_id"] = \
            api_mastodon.get_status_id_from_url(home_server, home_token, post["url"])

    # Now, we'll contact the pg database to update the public.status_stats table.
    # We'll need to do a lookup on the status_id to see if it's already in the table.
    # If it is, we'll update the existing row with the new data.
    # If it isn't, we'll insert a new row.

    for post in all_trending_posts:
        if post["local_status_id"] is not None:
            logging.info(f"Updating {post['local_status_id']} in public.status_stats")
            pgupdate(
                conn,
                post["local_status_id"],
                post["reblogs_count"],
                post["favourites_count"],
            )
    return all_trending_posts
