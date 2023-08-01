"""API for Lemmy."""
import logging
import time
from datetime import UTC, datetime

import requests

from fedifetcher.helpers import helpers


def get_user_posts_from_url(
        parsed_url : tuple[str, str],
) -> list[dict[str, str]] | None:
    """Get a list of posts from a user."""
    logging.info(f"Getting posts from {parsed_url[0]} for user {parsed_url[1]}")
    url = f"https://{parsed_url[0]}/api/v3/user?username={parsed_url[1]}&sort=New&limit=50"
    response = helpers.get(url)

    try:
        if response.status_code == helpers.Response.OK:
            comments = [post["post"] for post in response.json()["comments"]]
            posts = [post["post"] for post in response.json()["posts"]]
            all_posts = comments + posts
            for post in all_posts:
                post["url"] = post["ap_id"]
            return all_posts
    except requests.HTTPError:
        logging.error(
f"Error getting user posts for user {parsed_url[1]}: {response.text}")
    except requests.JSONDecodeError:
        logging.error(
f"Error decoding JSON for user {parsed_url[1]}. \
{parsed_url[0]} may not be a Lemmy instance.")
    except Exception:
        logging.exception(
f"Error getting user posts from {url}")
        return None

def get_community_posts_from_url(
        parsed_url : tuple[str, str]) -> list[dict[str, str]] | None:
    """Get a list of posts from a community."""
    logging.info(
        f"Getting posts from {parsed_url[0]} for community {parsed_url[1]}")
    try:
        url = f"https://{parsed_url[0]}/api/v3/post/list?community_name={parsed_url[1]}&sort=New&limit=50"
        response = helpers.get(url)
        if response.status_code == helpers.Response.OK:
            posts = [post["post"] for post in response.json()["posts"]]
            for post in posts:
                post["url"] = post["ap_id"]
            return posts
    except requests.exceptions.Timeout:
        logging.error(
f"Timeout getting posts for community {parsed_url[1]}")
    except requests.exceptions.RequestException:
        logging.exception(
f"Error getting posts for community {parsed_url[1]}")
    else:
        logging.error(
f"Error getting posts for community {parsed_url[1]}: {response.text}")
    return None

def get_comment_context(
    server: str,
    toot_id: str,
    toot_url: str,
) -> list[str]:
    """Get the URLs of the context toots of the given toot.

    Args:
    ----
    server (str): The server to get the context toots from.
    toot_id (str): The ID of the toot to get the context toots for.
    toot_url (str): The URL of the toot to get the context toots for.

    Returns:
    -------
    list[str]: The URLs of the context toots of the given toot.
    """
    logging.info(f"Getting context for comment {toot_url}")
    comment = f"https://{server}/api/v3/comment?id={toot_id}"
    try:
        resp = helpers.get(comment)
    except Exception as ex:
        logging.error(
f"Error getting comment {toot_id} from {toot_url}. Exception: {ex}")
        return []
    if resp.status_code == helpers.Response.OK:
        try:
            res = resp.json()
            post_id = res["comment_view"]["comment"]["post_id"]
            return get_comments_urls(server, post_id, toot_url)
        except Exception as ex:
            logging.error(
f"Error parsing context for comment {toot_url}. Exception: {ex}")
        return []
    if resp.status_code == helpers.Response.TOO_MANY_REQUESTS:
        reset = datetime.strptime(resp.headers["x-ratelimit-reset"],
            "%Y-%m-%dT%H:%M:%S.%fZ").astimezone(UTC)
        logging.warning(
f"Rate Limit hit when getting context for {toot_url}. \
Waiting to retry at {resp.headers['x-ratelimit-reset']}")
        time.sleep((reset - datetime.now(UTC)).total_seconds() + 1)
        return get_comment_context(server, toot_id, toot_url)

    return []

def get_comments_urls(  # noqa: PLR0912
        server : str,
        post_id : str,
        toot_url : str,
        ) -> list[str]:
    """Get the URLs of the comments of the given post.

    Args:
    ----
    server (str): The server to get the comments from.
    post_id (str): The ID of the post to get the comments for.
    toot_url (str): The URL of the post to get the comments for.

    Returns:
    -------
    list[str]: The URLs of the comments of the given post.
    """
    logging.info(f"Getting comments for post {toot_url}")
    urls = []
    url = f"https://{server}/api/v3/post?id={post_id}"
    try:
        resp = helpers.get(url)
    except Exception as ex:
        logging.error(f"Error getting post {post_id} from {toot_url}. Exception: {ex}")
        return []

    if resp.status_code == helpers.Response.OK:
        try:
            res = resp.json()
            if res["post_view"]["counts"]["comments"] == 0:
                return []
            urls.append(res["post_view"]["post"]["ap_id"])
        except Exception as ex:
            logging.error(f"Error parsing post {post_id} from {toot_url}. \
                        Exception: {ex}")

    url = f"https://{server}/api/v3/comment/list?post_id={post_id}&sort=New&limit=50"
    try:
        resp = helpers.get(url)
    except Exception as ex:
        logging.error(f"Error getting comments for post {post_id} from {toot_url}. \
Exception: {ex}")
        return []

    if resp.status_code == helpers.Response.OK:
        try:
            res = resp.json()
            list_of_urls = \
                [comment_info["comment"]["ap_id"] for comment_info in res["comments"]]
            logging.info(f"Got {len(list_of_urls)} comments for post {toot_url}")
            urls.extend(list_of_urls)
        except Exception as ex:
            logging.error(
f"Error parsing comments for post {toot_url}. Exception: {ex}")
        else:
            return urls
    elif resp.status_code == helpers.Response.TOO_MANY_REQUESTS:
        reset = datetime.strptime(resp.headers["x-ratelimit-reset"],
            "%Y-%m-%dT%H:%M:%S.%fZ").astimezone(UTC)
        logging.info(f"Rate Limit hit when getting comments for {toot_url}. Waiting to \
                    retry at {resp.headers['x-ratelimit-reset']}")
        time.sleep((reset - datetime.now(UTC)).total_seconds() + 1)
        return get_comments_urls(server, post_id, toot_url)

    logging.error(
f"Error getting comments for post {toot_url}. Status code: {resp.status_code}")
    return []
