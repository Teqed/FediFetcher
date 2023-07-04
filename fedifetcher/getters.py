"""Functions to get data from Fediverse servers."""
import itertools
import json
import re
import time
from collections.abc import Generator, Iterable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import requests
from dateutil import parser

from fedifetcher.ordered_set import OrderedSet

from . import helpers, parsers


def get_notification_users(
        server : str,
        access_token : str,
        known_users : OrderedSet,
        max_age : int = 24,
        ) -> list[str]:
    """Get a list of users that have interacted with the user in last `max_age` hours.

    Args:
    ----
    server (str): The server to get the notifications from.
    access_token (str): The access token to use for authentication.
    known_users (list[str]): A list of known users.
    max_age (int, optional): The maximum age of the notifications to consider. \
        Defaults to 24.

    Returns:
    -------
    list[str]: A list of users that have interacted with the user in the last \
        `max_age` hours.

    """
    since = datetime.now(
        datetime.now(UTC).astimezone().tzinfo) - timedelta(hours=max_age)
    notifications = get_paginated_mastodon(f"https://{server}/api/v1/notifications",
        int(since.timestamp()), headers={
        "Authorization": f"Bearer {access_token}",
    })
    notification_users = []
    for notification in notifications:
        notification_date = parser.parse(notification["created_at"])
        if(notification_date >= since and notification["account"] not in \
                notification_users):
            notification_users.append(notification["account"])

    new_notification_users = filter_known_users(notification_users, known_users)

    helpers.log(f"Found {len(notification_users)} users in notifications, \
        {len(new_notification_users)} of which are new")

    return [user["account"] for user in filter_known_users(
                                            notification_users, known_users)]

def get_bookmarks(
        server : str,
        access_token : str,
        limit : int = 50,
        ) -> list[dict]:
    """Get a list of bookmarked posts.

    Args:
    ----
    server (str): The server to get the bookmarks from.
    access_token (str): The access token to use for authentication.
    limit (int): The maximum number of posts to get.

    Returns:
    -------
    list[dict]: A list of bookmarked posts.

    """
    return get_paginated_mastodon(f"https://{server}/api/v1/bookmarks", limit, {
        "Authorization": f"Bearer {access_token}",
    })

def get_favourites(
        server : str,
        access_token : str,
        limit : int = 50,
        ) -> list[dict]:
    """Get a list of favourited posts.

    Args:
    ----
    server (str): The server to get the favourites from.
    access_token (str): The access token to use for authentication.
    limit (int): The maximum number of posts to get.


    Returns:
    -------
    list[dict]: A list of favourited posts.

    """
    return get_paginated_mastodon(f"https://{server}/api/v1/favourites", limit, {
        "Authorization": f"Bearer {access_token}",
    })

def get_user_posts(  # noqa: PLR0911, PLR0912, C901
        user : dict[str, str],
        know_followings : OrderedSet,
        server : str,
        ) -> list[dict[str, str]] | None:
    """Get a list of posts from a user.

    Args:
    ----
    user (dict): The user to get the posts from.
    know_followings (set[str]): A set of known followings.
    server (str): The server to get the posts from.


    Returns:
    -------
    list[dict] | None: A list of posts from the user, or None if the user \
        couldn't be fetched.

    """
    parsed_url = parsers.user(user["url"])

    if parsed_url is None:
        # We are adding it as 'known' anyway, because we won't be able to fix this.
        know_followings.add(user["acct"])
        return None

    if(parsed_url[0] == server):
        helpers.log(f"{user['acct']} is a local user. Skip")
        know_followings.add(user["acct"])
        return None
    if re.match(r"^https:\/\/[^\/]+\/c\/", user["url"]):
        try:
            url = f"https://{parsed_url[0]}/api/v3/post/list?community_name={parsed_url[1]}&sort=New&limit=50"
            response = helpers.get(url)

            if(response.status_code == helpers.Response.OK):
                posts = [post["post"] for post in response.json()["posts"]]
                for post in posts:
                    post["url"] = post["ap_id"]
                return posts

        except Exception as ex:
            helpers.log(f"Error getting community posts for community {parsed_url[1]}: \
{ex}")
        return None

    if re.match(r"^https:\/\/[^\/]+\/u\/", user["url"]):
        try:
            url = f"https://{parsed_url[0]}/api/v3/user?username={parsed_url[1]}&sort=New&limit=50"
            response = helpers.get(url)

            if(response.status_code == helpers.Response.OK):
                comments = [post["post"] for post in response.json()["comments"]]
                posts = [post["post"] for post in response.json()["posts"]]
                all_posts = comments + posts
                for post in all_posts:
                    post["url"] = post["ap_id"]
                return all_posts

        except Exception as ex:
            helpers.log(f"Error getting user posts for user {parsed_url[1]}: {ex}")
        return None

    try:
        user_id = get_user_id(parsed_url[0], parsed_url[1])
    except Exception as ex:
        helpers.log(f"Error getting user ID for user {user['acct']}: {ex}")
        return None

    try:
        url = f"https://{parsed_url[0]}/api/v1/accounts/{user_id}/statuses?limit=40"
        response = helpers.get(url)

        if(response.status_code == helpers.Response.OK):
            return response.json()
        if response.status_code == helpers.Response.NOT_FOUND:
            msg = f"User {user['acct']} was not found on server {parsed_url[0]}"
            raise Exception(
                msg,
            )
        msg = f"Error getting URL {url}. Status code: {response.status_code}"
        raise Exception(
            msg,
        )
    except Exception as ex:
        helpers.log(f"Error getting posts for user {user['acct']}: {ex}")
        return None

def get_new_follow_requests(
        server : str,
        access_token : str,
        limit : int, # = 40,
        known_followings : OrderedSet,
        ) -> list[dict]:
    """Get any new follow requests for the specified user.

    Args:
    ----
    server (str): The server to get the follow requests from.
    access_token (str): The access token to use for authentication.
    limit (int): The maximum number of follow requests to get.
    known_followings (set[str]): A set of known followings.


    Returns:
    -------
    list[dict]: A list of follow requests.
    """
    follow_requests = get_paginated_mastodon(f"https://{server}/api/v1/follow_requests",
        limit, {
        "Authorization": f"Bearer {access_token}",
    })

    # Remove any we already know about
    new_follow_requests = filter_known_users(
        list(follow_requests), known_followings)

    helpers.log(f"Got {len(follow_requests)} follow_requests, \
{len(new_follow_requests)} of which are new")

    return new_follow_requests

def get_new_followers(
        server : str,
        user_id : str,
        limit : int, # = 40,
        known_followers : OrderedSet,
        ) -> list[dict]:
    """Get any new followings for the specified user, up to the max number provided.

    Args:
    ----
    server (str): The server to get the followers from.
    user_id (str): The ID of the user to get the followers for.
    limit (int): The maximum number of followers to get.
    known_followers (set[str]): A set of known followers.



    Returns:
    -------
    list[dict]: A list of followers.
    """
    followers = get_paginated_mastodon(
        f"https://{server}/api/v1/accounts/{user_id}/followers", limit)

    # Remove any we already know about
    new_followers = filter_known_users(
        list(followers), known_followers)

    helpers.log(f"Got {len(followers)} followers, \
                {len(new_followers)} of which are new")

    return new_followers

def get_new_followings(
        server : str,
        user_id : str,
        limit : int, # = 40,
        known_followings : OrderedSet,
        ) -> list[dict]:
    """Get any new followings for the specified user, up to the max number provided.

    Args:
    ----
    server (str): The server to get the followings from.
    user_id (str): The ID of the user to get the followings for.
    limit (int): The maximum number of followings to get.
    known_followings (set[str]): A set of known followings.


    Returns:
    -------
    list[dict]: A list of followings.
    """
    following = get_paginated_mastodon(
        f"https://{server}/api/v1/accounts/{user_id}/following", limit)

    # Remove any we already know about
    new_followings = filter_known_users(
        list(following), known_followings)

    helpers.log(f"Got {len(following)} followings, \
                {len(new_followings)} of which are new")

    return new_followings

def get_user_id(
        server : str,
        user : str | None = None,
        access_token : str | None = None,
        ) -> str:
    """Get the user id from the server, using a username.

    Args:
    ----
    server (str): The server to get the user ID from.
    user (str): The user name to get the ID for.
    access_token (str): The access token to use for authentication.


    Returns:
    -------
    str: The user ID.

    Raises:
    ------
    Exception: If the user is not found, or if the URL returns an error.
    """
    headers = {}

    if user:
        url = f"https://{server}/api/v1/accounts/lookup?acct={user}"
    elif access_token:
        url = f"https://{server}/api/v1/accounts/verify_credentials"
        headers = {
            "Authorization": f"Bearer {access_token}",
        }
    else:
        msg = "You must supply either a user name or an access token, to get an user ID"
        raise Exception(
            msg)

    response = helpers.get(url, headers=headers)

    if response.status_code == helpers.Response.OK:
        return response.json()["id"]
    if response.status_code == helpers.Response.NOT_FOUND:
        msg = f"User {user} was not found on server {server}."
        raise Exception(
            msg,
        )
    msg = f"Error getting URL {url}. Status code: {response.status_code}"
    raise Exception(
        msg,
    )

def get_timeline(
    server: str,
    access_token: str,
    limit: int, # = 40,
) -> Iterator[dict]:
    """Get all posts in the user's home timeline.

    Args:
    ----
    server (str): The server to get the timeline from.
    access_token (str): The access token to use for authentication.
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
    url = f"https://{server}/api/v1/timelines/home"

    try:
        response = get_toots(url, access_token)

        if response.status_code == helpers.Response.OK:
            toots = response.json()
        elif response.status_code == helpers.Response.UNAUTHORIZED:
            msg = f"Error getting URL {url}. Status code: {response.status_code}. \
                Ensure your access token is correct"
            raise Exception(msg)
        elif response.status_code == helpers.Response.FORBIDDEN:
            msg = f"Error getting URL {url}. Status code: {response.status_code}. \
            Make sure you have the read:statuses scope enabled for your access token."
            raise Exception(msg)
        else:
            msg = f"Error getting URL {url}. Status code: {response.status_code}"
            raise Exception(msg)

        # Yield each toot from the response
        yield from toots

        # Paginate as needed
        while len(toots) < limit and "next" in response.links:
            response = get_toots(response.links["next"]["url"], access_token)
            toots = response.json()
            yield from toots
    except Exception as ex:
        helpers.log(f"Error getting timeline toots: {ex}")
        raise

    helpers.log(f"Found {len(toots)} toots in timeline")

def get_toots(
        url : str,
        access_token : str,
        ) -> requests.Response:
    """Get toots from the specified URL.

    Args:
    ----
    url (str): The URL to get the toots from.
    access_token (str): The access token to use for authentication.


    Returns:
    -------
    requests.Response: The response from the server.


    Raises:
    ------
    Exception: If the access token is invalid.
    Exception: If the access token does not have the correct scope.
    Exception: If the server returns an unexpected status code.
    """
    response = helpers.get( url, headers={
        "Authorization": f"Bearer {access_token}",
    })

    if response.status_code == helpers.Response.OK:
        return response
    if response.status_code == helpers.Response.UNAUTHORIZED:
        msg = f"Error getting URL {url}. Status code: {response.status_code}. It looks like your access token is incorrect."
        raise Exception(
            msg,
        )
    if response.status_code == helpers.Response.FORBIDDEN:
        msg = f"Error getting URL {url}. Status code: {response.status_code}. Make sure you have the read:statuses scope enabled for your access token."
        raise Exception(
            msg,
        )
    msg = f"Error getting URL {url}. Status code: {response.status_code}"
    raise Exception(
        msg,
    )

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
    since = datetime.now(UTC) - timedelta(days=reply_interval_hours / 24 + 1)
    url = f"https://{server}/api/v1/admin/accounts"
    resp = helpers.get(url, headers={
        "Authorization": f"Bearer {access_token}",
    })
    if resp.status_code == helpers.Response.OK:
        for user in resp.json():
            last_status_at = user["account"]["last_status_at"]
            if last_status_at:
                last_active = datetime.strptime(
                    last_status_at, "%Y-%m-%d").astimezone(UTC)
                if last_active > since:
                    helpers.log(f"Found active user: {user['username']}")
                    yield user["id"]
    elif resp.status_code == helpers.Response.UNAUTHORIZED:
        msg = f"Error getting user IDs on server {server}. Status code: {resp.status_code}. Ensure your access token is correct"
        raise Exception(
        msg,
        )
    elif resp.status_code == helpers.Response.FORBIDDEN:
        msg = f"Error getting user IDs on server {server}. Status code: {resp.status_code}. Make sure you have the admin:read:accounts scope enabled for your access token."
        raise Exception(
        msg,
        )
    else:
        msg = f"Error getting user IDs on server {server}. Status code: {resp.status_code}"
        raise Exception(
        msg,
        )

def get_all_reply_toots(
    server: str,
    user_ids: Iterable[str],
    access_token: str,
    seen_urls: OrderedSet,
    reply_interval_hours: int,
) -> Iterator[dict[str, Any]]:
    """Get all replies to other users by the given users in the last day.

    Args:
    ----
    server (str): The server to get the toots from.
    user_ids (Iterable[str]): The user IDs to get the toots from.
    access_token (str): The access token to use for authentication.
    seen_urls (OrderedSet[str]): The URLs that have already been seen.
    reply_interval_hours (int): The number of hours to look back for replies.

    Yields:
    ------
    dict[str, Any]: A toot.

    Raises:
    ------
    Exception: If the access token is invalid.
    Exception: If the access token does not have the correct scope.
    Exception: If the server returns an unexpected status code.
    """
    replies_since = datetime.now(UTC) - timedelta(hours=reply_interval_hours)
    for user_id in user_ids:
        yield from get_reply_toots(
            user_id,
            server,
            access_token,
            seen_urls,
            replies_since,
        )

def get_reply_toots(
        user_id : str,
        server : str,
        access_token : str,
        seen_urls : OrderedSet,
        reply_since : datetime,
        ) -> Iterator[dict[str, Any]]:
    """Get replies by the user to other users since the given date.

    Args:
    ----
    user_id (str): The user ID to get the replies from.
    server (str): The server to get the replies from.
    access_token (str): The access token to use for authentication.
    seen_urls (set[str]): The URLs that have already been seen.
    reply_since (datetime): The date to look back to for replies.

    Returns:
    -------
    list[dict[str, Any]]: A list of toots.

    Raises:
    ------
    Exception: If the access token is invalid.
    Exception: If the access token does not have the correct scope.
    Exception: If the server returns an unexpected status code.
    """
    url = f"https://{server}/api/v1/accounts/{user_id}/statuses?exclude_replies=false&limit=40"

    try:
        resp = helpers.get(url, headers={
            "Authorization": f"Bearer {access_token}",
        })
    except Exception as ex:
        helpers.log(
            f"Error getting replies for user {user_id} on server {server}: {ex}",
        )
        return iter([])

    if resp.status_code == helpers.Response.OK:
        toots = [
            toot
            for toot in resp.json()
            if toot["in_reply_to_id"]
            and toot["url"] not in seen_urls
            and datetime.strptime(
        toot["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ").astimezone(UTC) > reply_since
        ]
        for toot in toots:
            helpers.log(f"Found reply toot: {toot['url']}")
        return iter(toots)
    if resp.status_code == helpers.Response.FORBIDDEN:
        msg = f"Error getting replies for user {user_id} on server {server}. Status code: {resp.status_code}. Make sure you have the read:statuses scope enabled for your access token."
        raise Exception(
            msg,
        )

    msg = f"Error getting replies for user {user_id} on server {server}. Status code: {resp.status_code}"
    raise Exception(
        msg,
    )

def get_all_known_context_urls(
    server: str,
    reply_toots: Iterator[dict[str, str]],
    parsed_urls: dict[str, tuple[str | None, str | None]],
) -> filter[str]:
    """Get the context toots of the given toots from their original server.

    Args:
    ----
    server (str): The server to get the context toots from.
    reply_toots (Iterator[Optional[Dict[str, Optional[str]]]]): \
        The toots to get the context toots for.
    parsed_urls (Dict[str, Optional[Tuple[str, str]]]): \
        The parsed URL of the toots.

    Returns:
    -------
    filter[str]: The URLs of the context toots.

    Raises:
    ------
    Exception: If the server returns an unexpected status code.
    """
    known_context_urls = []

    if reply_toots is not None:
        for toot in reply_toots:
            if toot is not None and toot_has_parseable_url(toot, parsed_urls):
                reblog = toot.get("reblog")
                if isinstance(reblog, str):
                    try:
                        reblog_dict = json.loads(reblog)
                        url = reblog_dict.get("url")
                        if url is None:
                            helpers.log("Error accessing URL in the boosted toot")
                            continue
                    except json.JSONDecodeError:
                        helpers.log("Error decoding JSON in the boosted toot")
                        continue
                elif isinstance(reblog, dict):
                    url = reblog.get("url")
                    if url is None:
                        helpers.log("Error accessing URL in the boosted toot")
                        continue
                elif toot.get("url") is not None:
                    url = str(toot["url"])
                else:
                    helpers.log("Error accessing URL in the toot")
                    continue

                parsed_url = parsers.post(url, parsed_urls)
                if parsed_url and parsed_url[0] and parsed_url[1]:
                    context = get_toot_context(parsed_url[0], parsed_url[1], url)
                    if context:
                        known_context_urls.extend(context)
                    else:
                        helpers.log(f"Error getting context for toot {url}")
                else:
                    helpers.log(f"Error parsing URL for toot {url}")

    return filter(
        lambda url: not url.startswith(f"https://{server}/"), known_context_urls)



def get_all_replied_toot_server_ids(
    server: str,
    reply_toots: Iterator[dict[str, Any]],
    replied_toot_server_ids: dict[str, str | None],
    parsed_urls: dict[str, tuple[str | None, str | None]],
) -> filter[tuple[str | None, str | None]]:
    """Get the server and ID of the toots the given toots replied to.

    Args:
    ----
    server (str): The server to get the replied toots from.
    reply_toots (Iterator[dict[str, Any]]): The toots to get the replied toots for.
    replied_toot_server_ids (dict[str, str | None]): The server and ID of the toots \
        that have already been replied to.
    parsed_urls (dict[str, dict[str, str] | None]): The parsed URLs of the toots.

    Returns:
    -------
    filter[str | tuple[str, tuple[str, str]] | None]: The server and ID of the toots \
        the given toots replied to.
    """
    return filter(
        lambda replied_to: replied_to is not None,
        (get_replied_toot_server_id(
                server,
                toot,
                replied_toot_server_ids,
                parsed_urls,
            ) for toot in reply_toots),
    )

def get_replied_toot_server_id(
    server: str,
    toot: dict[str, Any],
    replied_toot_server_ids: dict[str, str | None],
    parsed_urls: dict[str, tuple[str | None, str | None]],
) -> tuple[str | None, str | None]:
    """Get the server and ID of the toot the given toot replied to."""
    in_reply_to_id = toot["in_reply_to_id"]
    in_reply_to_account_id = toot["in_reply_to_account_id"]
    mentions = [
        mention
        for mention in toot["mentions"]
        if mention["id"] == in_reply_to_account_id
    ]
    if len(mentions) < 1:
        return (None, None)

    mention = mentions[0]

    o_url = f"https://{server}/@{mention['acct']}/{in_reply_to_id}"
    if o_url in replied_toot_server_ids:
        if replied_toot_server_ids[o_url] is None:
            return (None, None)
        if isinstance(replied_toot_server_ids[o_url], str):
            ## Missing code goes here
            cast(str, replied_toot_server_ids[o_url]).split(",")
            return (
                    cast(str, replied_toot_server_ids[o_url])[0],
                    cast(str, replied_toot_server_ids[o_url])[1],
                    )

    url = get_redirect_url(o_url)

    if url is None:
        return (None, None)

    match = parsers.post(url, parsed_urls)
    if match:
        if match[0] is not None and match[1] is not None:
            replied_toot_server_ids[o_url] = f"{url},{match[0]},{match[1]}"
            return (match[0], match[1])
        replied_toot_server_ids[o_url] = None
        return (None, None)

    helpers.log(f"Error parsing toot URL {url}")
    replied_toot_server_ids[o_url] = None
    return (None, None)


def get_redirect_url(url : str) -> str | None:
    """Get the URL given URL redirects to.

    Args:
    ----
    url (str): The URL to get the redirect URL for.

    Returns:
    -------
    str | None: The URL the given URL redirects to, or None if the URL does not \
        redirect.
    """
    try:
        resp = requests.head(url, allow_redirects=False, timeout=5,headers={
            "User-Agent": "FediFetcher (https://go.thms.uk/mgr)",
        })
    except Exception as ex:
        helpers.log(f"Error getting redirect URL for URL {url}. Exception: {ex}")
        return None

    if resp.status_code == helpers.Response.OK:
        return url
    if resp.status_code == helpers.Response.FOUND:
        redirect_url = resp.headers["Location"]
        helpers.log(f"Discovered redirect for URL {url}")
        return redirect_url
    helpers.log(
        f"Error getting redirect URL for URL {url}. Status code: {resp.status_code}",
    )
    return None

def get_all_context_urls(
    server: str,
    replied_toot_ids: filter[tuple[str | None, str | None]],
) -> filter[str]:
    """Get the URLs of the context toots of the given toots.

    Args:
    ----
    server (str): The server to get the context toots from.
    replied_toot_ids (filter[tuple[str | None, str | None]]): The server and ID of the \
        toots to get the context toots for.

    Returns:
    -------
    filter[str]: The URLs of the context toots of the given toots.
    """
    return cast(filter[str], filter(
        lambda url: not str(url).startswith(f"https://{server}/"),
        itertools.chain.from_iterable(
            get_toot_context(server, toot_id, url)
            for (url, (s, toot_id)) in cast(filter[tuple[str, str]], replied_toot_ids)
        ),
    ))

def get_toot_context(
        server : str,
        toot_id : str,
        toot_url : str,
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
    if toot_url.find("/comment/") != -1:
        return get_comment_context(server, toot_id, toot_url)
    if toot_url.find("/post/") != -1:
        return get_comments_urls(server, toot_id, toot_url)
    url = f"https://{server}/api/v1/statuses/{toot_id}/context"
    try:
        resp = helpers.get(url)
    except Exception as ex:
        helpers.log(f"Error getting context for toot {toot_url}. Exception: {ex}")
        return []

    if resp.status_code == helpers.Response.OK:
        try:
            res = resp.json()
            helpers.log(f"Got context for toot {toot_url}")
            return [toot["url"] for toot in (res["ancestors"] + res["descendants"])]
        except Exception as ex:
            helpers.log(f"Error parsing context for toot {toot_url}. Exception: {ex}")
        return []
    if resp.status_code == helpers.Response.TOO_MANY_REQUESTS:
        reset = datetime.strptime(resp.headers["x-ratelimit-reset"],
            "%Y-%m-%dT%H:%M:%S.%fZ").astimezone(UTC)
        helpers.log(f"Rate Limit hit when getting context for {toot_url}. \
                    Waiting to retry at {resp.headers['x-ratelimit-reset']}")
        time.sleep((reset - datetime.now(UTC)).total_seconds() + 1)
        return get_toot_context(server, toot_id, toot_url)

    helpers.log(
        f"Error getting context for toot {toot_url}. Status code: {resp.status_code}",
    )
    return []

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
    comment = f"https://{server}/api/v3/comment?id={toot_id}"
    try:
        resp = helpers.get(comment)
    except Exception as ex:
        helpers.log(f"Error getting comment {toot_id} from {toot_url}. Exception: {ex}")
        return []
    if resp.status_code == helpers.Response.OK:
        try:
            res = resp.json()
            post_id = res["comment_view"]["comment"]["post_id"]
            return get_comments_urls(server, post_id, toot_url)
        except Exception as ex:
            helpers.log(f"Error parsing context for comment {toot_url}. \
                        Exception: {ex}")
        return []
    if resp.status_code == helpers.Response.TOO_MANY_REQUESTS:
        reset = datetime.strptime(resp.headers["x-ratelimit-reset"],
            "%Y-%m-%dT%H:%M:%S.%fZ").astimezone(UTC)
        helpers.log(f"Rate Limit hit when getting context for {toot_url}. \
                    Waiting to retry at {resp.headers['x-ratelimit-reset']}")
        time.sleep((reset - datetime.now(UTC)).total_seconds() + 1)
        return get_comment_context(server, toot_id, toot_url)

    return []

def get_comments_urls(
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
    urls = []
    url = f"https://{server}/api/v3/post?id={post_id}"
    try:
        resp = helpers.get(url)
    except Exception as ex:
        helpers.log(f"Error getting post {post_id} from {toot_url}. Exception: {ex}")
        return []

    if resp.status_code == helpers.Response.OK:
        try:
            res = resp.json()
            if res["post_view"]["counts"]["comments"] == 0:
                return []
            urls.append(res["post_view"]["post"]["ap_id"])
        except Exception as ex:
            helpers.log(f"Error parsing post {post_id} from {toot_url}. \
                        Exception: {ex}")

    url = f"https://{server}/api/v3/comment/list?post_id={post_id}&sort=New&limit=50"
    try:
        resp = helpers.get(url)
    except Exception as ex:
        helpers.log(f"Error getting comments for post {post_id} from {toot_url}. \
Exception: {ex}")
        return []

    if resp.status_code == helpers.Response.OK:
        try:
            res = resp.json()
            list_of_urls = \
                [comment_info["comment"]["ap_id"] for comment_info in res["comments"]]
            helpers.log(f"Got {len(list_of_urls)} comments for post {toot_url}")
            urls.extend(list_of_urls)
        except Exception as ex:
            helpers.log(f"Error parsing comments for post {toot_url}. Exception: {ex}")
        else:
            return urls
    elif resp.status_code == helpers.Response.TOO_MANY_REQUESTS:
        reset = datetime.strptime(resp.headers["x-ratelimit-reset"],
            "%Y-%m-%dT%H:%M:%S.%fZ").astimezone(UTC)
        helpers.log(f"Rate Limit hit when getting comments for {toot_url}. Waiting to \
                    retry at {resp.headers['x-ratelimit-reset']}")
        time.sleep((reset - datetime.now(UTC)).total_seconds() + 1)
        return get_comments_urls(server, post_id, toot_url)

    helpers.log(f"Error getting comments for post {toot_url}. \
                Status code: {resp.status_code}")
    return []

def get_paginated_mastodon(
        url : str,
        limit : int = 40,
        headers : dict[str, str] = {},
        timeout : int = 10,
        max_tries : int = 3,
        ) -> list[dict[str, Any]]:
    """Make a paginated request to mastodon.

    Args:
    ----
    url (str): The URL to make the request to.
    limit (int | str, optional): The number of items to get per request. Defaults to 40.
    headers (dict[str, str], optional): The headers to use for the request. \
        Defaults to {}.
    timeout (int, optional): The timeout for the request. Defaults to 10.
    max_tries (int, optional): The maximum number of times to retry the request. \
        Defaults to 3.

    Raises:
    ------
    Exception: If the request fails.
    """
    furl = f"{url}?limit={limit}" if isinstance(limit, int) else url

    response = helpers.get(furl, headers, timeout, max_tries)

    if response.status_code != helpers.Response.OK:
        if response.status_code == helpers.Response.UNAUTHORIZED:
            msg = f"Error getting URL {url}. Status code: {response.status_code}. \
                Ensure your access token is correct"
            raise Exception(
                msg,
            )
        if response.status_code == helpers.Response.FORBIDDEN:
            msg = f"Error getting URL {url}. Status code: {response.status_code}. \
                Make sure you have the correct scopes enabled for your access token."
            raise Exception(
                msg,
            )
        msg = f"Error getting URL {url}. Status code: {response.status_code}"
        raise Exception(
            msg,
        )

    result = response.json()

    if(isinstance(limit, int)):
        while len(result) < limit and "next" in response.links:
            response = helpers.get(
                response.links["next"]["url"], headers, timeout, max_tries)
            result = result + response.json()
    else:
        while parser.parse(result[-1]["created_at"]) >= limit \
                and "next" in response.links:
            response = helpers.get(
                response.links["next"]["url"], headers, timeout, max_tries)
            result = result + response.json()

    return result

def filter_known_users(
        users : list[dict[str, str]],
        known_users : OrderedSet,
        ) -> list[dict[str, str]]:
    """Filter out users that are already known.

    Args:
    ----
    users (list[dict[str, str]]): The users to filter.
    known_users (list[str]): The users that are already known.

    Returns:
    -------
    list[dict[str, str]]: The users that are not already known.
    """
    return list(filter(
        lambda user: user["acct"] not in known_users,
        users,
    ))

def toot_has_parseable_url(
    toot: dict[str, Any],
    parsed_urls: dict[str, tuple[str | None, str | None]],
) -> bool:
    """Check if the given toot has a parseable URL.

    Args:
    ----
    toot (dict[str, Any]): The toot to check.
    parsed_urls (dict[str, tuple[str, str] | None]): \
        The URLs that have already been parsed.

    Returns:
    -------
    bool: True if the toot has a parseable URL, False otherwise.
    """
    url = toot["url"] if toot["reblog"] is None else toot["reblog"]["url"]
    parsed = parsers.post(url, parsed_urls)
    return parsed is not None
