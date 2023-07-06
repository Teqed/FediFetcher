"""API for Lemmy."""
import logging

from fedifetcher import helpers


def get_user_posts_from_url(
        parsed_url : tuple[str, str],
) -> list[dict[str, str]] | None:
    """Get a list of posts from a user."""
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
    except:
        logging.exception(
f"Error getting user posts from {url}")
        return None

def get_community_posts_from_url(
        parsed_url : tuple[str, str]) -> list[dict[str, str]] | None:
    """Get a list of posts from a community."""
    url = f"https://{parsed_url[0]}/api/v3/post/list?community_name={parsed_url[1]}&sort=New&limit=50"
    response = helpers.get(url)
    if response.status_code == helpers.Response.OK:
        posts = [post["post"] for post in response.json()["posts"]]
        for post in posts:
            post["url"] = post["ap_id"]
        return posts
    logging.error(
f"Error getting community posts for community {parsed_url[1]}: {response.text}")
    return None
