"""Pull trending posts from a list of Mastodon servers, using tokens."""


import logging
import re
from datetime import UTC, datetime

import psycopg2

from fedifetcher import api_mastodon, parsers


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
    all_trending_posts: dict[str, dict[str, str]] = {}

    for key in external_tokens:
        logging.info(f"Finding trending posts on {key}")
        trending_posts = api_mastodon.get_trending_posts(key, external_tokens[key])

        for post in trending_posts:
            post_url: str = post["url"]
            if post_url in all_trending_posts:
                all_trending_posts[post_url]["reblogs_count"] \
                    += post["reblogs_count"]
                all_trending_posts[post_url]["favourites_count"] \
                    += post["favourites_count"]
            else:
                original = re.search(r"https?://[^/]*\b" + re.escape(key), post["url"])
                if not original:
                    original = parsers.post(post["url"])
                    if original and original[0] and original[1]:
                        original_status = api_mastodon.get_status_by_id(
                                original[0], original[1], external_tokens)
                        if original_status:
                            original_status["reblogs_count"] += post["reblogs_count"]
                            original_status["favourites_count"] += \
                                post["favourites_count"]
                            logging.info(
                                f"Adding {post_url} to trending posts from origin")
                            all_trending_posts[post_url] = original_status
                            continue
                logging.info(f"Adding {post_url} to trending posts")
                all_trending_posts[post_url] = post

    # We're going to updaet the public.status_stats table with the trending posts.
    # We'll navigate by status_id, which we'll need to fetch from our home server,
    # since it's different from the status's home server's ID for it.
    # We can do a lookup on Mastodon API using the URL of the status.
    # We'll add this as a property to each trending post, named 'local_status_id'.
    for url in all_trending_posts:
        local_status_id = \
            api_mastodon.get_status_id_from_url(home_server, home_token, url)
        all_trending_posts[url]["local_status_id"] = \
            local_status_id if local_status_id else ""

    # Now, we'll contact the pg database to update the public.status_stats table.
    # We'll need to do a lookup on the status_id to see if it's already in the table.
    # If it is, we'll update the existing row with the new data.
    # If it isn't, we'll insert a new row.

    for url in all_trending_posts:
        post = all_trending_posts[url]
        if post["local_status_id"] is not None and post["local_status_id"] != "":
            logging.info(f"Updating {post['local_status_id']} in public.status_stats")
            pgupdate(
                conn,
                int(post["local_status_id"]),
                int(post["reblogs_count"]),
                int(post["favourites_count"]),
            )
    return list(all_trending_posts.values())
