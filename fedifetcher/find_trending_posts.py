"""Pull trending posts from a list of Mastodon servers, using tokens."""


import logging
import re
from datetime import UTC, datetime

from psycopg2 import Error, OperationalError, connect

from fedifetcher import api_mastodon, parsers


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

def find_trending_posts(
        home_server: str,
        home_token: str,
        external_feeds: list[str],
        external_tokens: dict[str, str],
        pgpassword: str,
        ) -> list[dict[str, str]]:
    """Pull trending posts from a list of Mastodon servers, using tokens."""
    logging.warning("Finding trending posts")

    # For each key in external_tokens, query its mastodon API for trending posts.
    # Later, we're going to compare these results to each other.
    trending_posts_dict: dict[str, dict[str, str]] = {}

    def add_post_to_dict(trending_post : dict[str, str],
                        fetched_from_domain : str) -> bool:
        """Add a trending post to the trending_posts_dict, if it's not already there.

        Args:
        ----
        trending_post (dict[str, str]): The trending post to add.
        fetched_from_domain (str): The domain the trending post was fetched from.

        Returns:
        -------
        bool: True if the post was original, False otherwise.
        """
        t_post_url = trending_post["url"]
        original = re.search(
            r"https?://([a-zA-Z0-9_-]+\.)*(?:" + re.escape(fetched_from_domain) \
                + ")(?:/.*)?", t_post_url)
        if original:
            logging.info(
        f"Adding original {t_post_url} to trending posts from {fetched_from_domain}")
            trending_posts_dict[t_post_url] = trending_post
            trending_posts_dict[t_post_url]["original"] = "Yes"
            logging.info(f"Reblogs: {trending_post['reblogs_count']} \
Favourites: {trending_post['favourites_count']}")
            return True
        if t_post_url in trending_posts_dict:
            if "original" not in trending_posts_dict[t_post_url]:
                logging.info(
                    f"Adding stats for {t_post_url} from {fetched_from_domain}")
                increment_count(t_post_url, trending_post)
                return False
            logging.info(
                f"Already seen {t_post_url} from {fetched_from_domain}")
            return True # We already have the original
        logging.info(
            f"Adding copy of {t_post_url} to trending posts from {fetched_from_domain}")
        logging.info(f"Reblogs: {trending_post['reblogs_count']} \
Favourites: {trending_post['favourites_count']}")
        trending_posts_dict[t_post_url] = trending_post
        return False

    def increment_count(post_url : str, incrementing_post : dict[str, str]) -> None:
        """Increment the reblogs_count and favourites_count of a post."""
        logging.info(f"Reblogs: {trending_posts_dict[post_url]['reblogs_count']} \
+= {incrementing_post['reblogs_count']}")
        trending_posts_dict[post_url]["reblogs_count"] \
            += incrementing_post["reblogs_count"]
        logging.info(f"Favourites: {trending_posts_dict[post_url]['favourites_count']} \
+= {incrementing_post['favourites_count']}")
        trending_posts_dict[post_url]["favourites_count"] \
            += incrementing_post["favourites_count"]

    domains_to_fetch = external_feeds
    logging.warning(f"Fetching trending posts from {len(domains_to_fetch)} domains:")
    for domain in domains_to_fetch:
        logging.warning(domain)
    domains_fetched = []
    remember_to_find_me : dict[str, list[str]] = {}
    for fetch_domain in external_feeds:
        logging.warning(f"Finding trending posts on {fetch_domain}")
        trending_posts = api_mastodon.get_trending_posts(
            fetch_domain, external_tokens.get(fetch_domain))
        domains_fetched.append(fetch_domain)
        domains_to_fetch.remove(fetch_domain)

        for post in trending_posts:
            post_url: str = post["url"]
            original = add_post_to_dict(post, fetch_domain)
            if original:
                continue
            parsed_url = parsers.post(post_url)
            if not parsed_url or not parsed_url[0] or not parsed_url[1]:
                logging.warning(f"Error parsing post URL {post_url}")
                continue
            if parsed_url[0] in domains_to_fetch:
                if parsed_url[0] not in remember_to_find_me:
                    remember_to_find_me[parsed_url[0]] = []
                remember_to_find_me[parsed_url[0]].append(parsed_url[1])
                continue
            if parsed_url[0] not in domains_fetched:
                logging.warning(f"Finding aux trending posts from {parsed_url[0]}")
                trending = api_mastodon.get_trending_posts(
                    parsed_url[0], external_tokens.get(parsed_url[0]))
                domains_fetched.append(parsed_url[0])
                if trending:
                    for t_post in trending:
                        if add_post_to_dict(t_post, parsed_url[0]) \
                                and t_post["url"] == post_url:
                            original = True
            if not original:
                remote = api_mastodon.get_status_by_id(
                    parsed_url[0], parsed_url[1], external_tokens)
                if remote and remote["url"] == post_url:
                    original = add_post_to_dict(remote, parsed_url[0])
            if not original:
                logging.warning(f"Couldn't find original for {post_url}")
        if fetch_domain in remember_to_find_me:
            logging.info(
f"Fetching {len(remember_to_find_me[fetch_domain])} \
less popular posts from {fetch_domain}")
            for status_id in remember_to_find_me[fetch_domain]:
                if status_id not in trending_posts_dict or \
                        "original" not in trending_posts_dict[status_id]:
                    logging.info(f"Fetching {status_id} from {fetch_domain}")
                    original_post = api_mastodon.get_status_by_id(
                        fetch_domain, status_id, external_tokens)
                    if original_post:
                        add_post_to_dict(original_post, fetch_domain)
                    else:
                        logging.warning(
                            f"Couldn't find {status_id} from {fetch_domain}")
            remember_to_find_me.pop(fetch_domain)

    for url, post in trending_posts_dict.items():
        local_status_id = api_mastodon.get_status_id_from_url(
            home_server, home_token, url)
        post["local_status_id"] = local_status_id if local_status_id else ""

    conn = connect(
    host="dreamer",
    port = 5432,
    database="mastodon_production",
    user="teq",
    password=pgpassword,
    )
    pgupdate = PostgreSQLUpdater(conn)

    """Update the status stats with the trending posts."""
    for _url, post in trending_posts_dict.items():
        local_status_id = post["local_status_id"]
        if local_status_id:
            logging.info(
f"Queueing stats for {local_status_id} with {post['reblogs_count']} reblogs \
and {post['favourites_count']} favourites")
            pgupdate.queue_update(
                int(local_status_id),
                int(post["reblogs_count"]),
                int(post["favourites_count"]),
            )
    pgupdate.commit_updates()

    return list(trending_posts_dict.values())
