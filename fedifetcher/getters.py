from datetime import datetime, timedelta
import helpers as helper
import time
from dateutil import parser
import re
import itertools
import requests
from parsers import parse_user_url

def get_notification_users(server, access_token, known_users, max_age):
    since = datetime.now(datetime.now().astimezone().tzinfo) - timedelta(hours=max_age)
    notifications = get_paginated_mastodon(f"https://{server}/api/v1/notifications",
        since, headers={
        "Authorization": f"Bearer {access_token}",
    })
    notification_users = []
    for notification in notifications:
        notificationDate = parser.parse(notification['created_at'])
        if(notificationDate >= since and notification['account'] not in \
                notification_users):
            notification_users.append(notification['account'])

    new_notification_users = filter_known_users(notification_users, known_users)

    helper.log(f"Found {len(notification_users)} users in notifications, \
        {len(new_notification_users)} of which are new")

    return new_notification_users

def get_bookmarks(server, access_token, limit):
    return get_paginated_mastodon(f"https://{server}/api/v1/bookmarks", limit, {
        "Authorization": f"Bearer {access_token}",
    })

def get_favourites(server, access_token, limit):
    return get_paginated_mastodon(f"https://{server}/api/v1/favourites", limit, {
        "Authorization": f"Bearer {access_token}",
    })

def get_user_posts(user, know_followings, server):
    parsed_url = parse_user_url(user['url'])

    if parsed_url is None:
        # We are adding it as 'known' anyway, because we won't be able to fix this.
        know_followings.add(user['acct'])
        return None

    if(parsed_url[0] == server):
        helper.log(f"{user['acct']} is a local user. Skip")
        know_followings.add(user['acct'])
        return None
    if re.match(r"^https:\/\/[^\/]+\/c\/", user['url']):
        try:
            url = f"https://{parsed_url[0]}/api/v3/post/list?community_name={parsed_url[1]}&sort=New&limit=50"
            response = helper.get(url)

            if(response.status_code == helper.Response.OK):
                posts = [post['post'] for post in response.json()['posts']]
                for post in posts:
                    post['url'] = post['ap_id']
                return posts

        except Exception as ex:
            helper.log(f"Error getting community posts for community {parsed_url[1]}: \
{ex}")
        return None

    if re.match(r"^https:\/\/[^\/]+\/u\/", user['url']):
        try:
            url = f"https://{parsed_url[0]}/api/v3/user?username={parsed_url[1]}&sort=New&limit=50"
            response = helper.get(url)

            if(response.status_code == helper.Response.OK):
                comments = [post['post'] for post in response.json()['comments']]
                posts = [post['post'] for post in response.json()['posts']]
                all_posts = comments + posts
                for post in all_posts:
                    post['url'] = post['ap_id']
                return all_posts

        except Exception as ex:
            helper.log(f"Error getting user posts for user {parsed_url[1]}: {ex}")
        return None

    try:
        user_id = get_user_id(parsed_url[0], parsed_url[1])
    except Exception as ex:
        helper.log(f"Error getting user ID for user {user['acct']}: {ex}")
        return None

    try:
        url = f"https://{parsed_url[0]}/api/v1/accounts/{user_id}/statuses?limit=40"
        response = helper.get(url)

        if(response.status_code == helper.Response.OK):
            return response.json()
        elif response.status_code == helper.Response.NOT_FOUND:
            raise Exception(
                f"User {user['acct']} was not found on server {parsed_url[0]}"
            )
        else:
            raise Exception(
                f"Error getting URL {url}. Status code: {response.status_code}"
            )
    except Exception as ex:
        helper.log(f"Error getting posts for user {user['acct']}: {ex}")
        return None

def get_new_follow_requests(server, access_token, limit, known_followings):
    """Get any new follow requests for the specified user, up to the max number \
        provided"""

    follow_requests = get_paginated_mastodon(f"https://{server}/api/v1/follow_requests",
        limit, {
        "Authorization": f"Bearer {access_token}",
    })

    # Remove any we already know about
    new_follow_requests = filter_known_users(follow_requests, known_followings)

    helper.log(f"Got {len(follow_requests)} follow_requests, \
{len(new_follow_requests)} of which are new")

    return new_follow_requests

def get_new_followers(server, user_id, limit, known_followers):
    """Get any new followings for the specified user, up to the max number provided"""
    followers = get_paginated_mastodon(
        f"https://{server}/api/v1/accounts/{user_id}/followers", limit)

    # Remove any we already know about
    new_followers = filter_known_users(followers, known_followers)

    helper.log(f"Got {len(followers)} followers, {len(new_followers)} of which are new")

    return new_followers

def get_new_followings(server, user_id, limit, known_followings):
    """Get any new followings for the specified user, up to the max number provided"""
    following = get_paginated_mastodon(
        f"https://{server}/api/v1/accounts/{user_id}/following", limit)

    # Remove any we already know about
    new_followings = filter_known_users(following, known_followings)

    helper.log(f"Got {len(following)} followings, {len(new_followings)} of which are new")

    return new_followings

def get_user_id(server, user = None, access_token = None):
    """Get the user id from the server, using a username"""

    headers = {}

    if user:
        url = f"https://{server}/api/v1/accounts/lookup?acct={user}"
    elif access_token:
        url = f"https://{server}/api/v1/accounts/verify_credentials"
        headers = {
            "Authorization": f"Bearer {access_token}",
        }
    else:
        raise Exception(
            'You must supply either a user name or an access token, to get an user ID')

    response = helper.get(url, headers=headers)

    if response.status_code == helper.Response.OK:
        return response.json()['id']
    elif response.status_code == helper.Response.NOT_FOUND:
        raise Exception(
            f"User {user} was not found on server {server}."
        )
    else:
        raise Exception(
            f"Error getting URL {url}. Status code: {response.status_code}"
        )

def get_timeline(server, access_token, limit):
    """Get all post in the user's home timeline"""

    url = f"https://{server}/api/v1/timelines/home"

    try:

        response = get_toots(url, access_token)

        if response.status_code == helper.Response.OK:
            toots = response.json()
        elif response.status_code == helper.Response.UNAUTHORIZED:
            raise Exception(
                f"Error getting URL {url}. Status code: {response.status_code}. "
                "Ensure your access token is correct"
            )
        elif response.status_code == helper.Response.FORBIDDEN:
            raise Exception(
                f"Error getting URL {url}. Status code: {response.status_code}. "
            "Make sure you have the read:statuses scope enabled for your access token."
            )
        else:
            raise Exception(
                f"Error getting URL {url}. Status code: {response.status_code}"
            )

        # Paginate as needed
        while len(toots) < limit and 'next' in response.links:
            response = get_toots(response.links['next']['url'], access_token)
            toots = toots + response.json()
    except Exception as ex:
        helper.log(f"Error getting timeline toots: {ex}")
        raise

    helper.log(f"Found {len(toots)} toots in timeline")

    return toots

def get_toots(url, access_token):
    response = helper.get( url, headers={
        "Authorization": f"Bearer {access_token}",
    })

    if response.status_code == helper.Response.OK:
        return response
    elif response.status_code == helper.Response.UNAUTHORIZED:
        raise Exception(
            f"Error getting URL {url}. Status code: {response.status_code}. "
            "It looks like your access token is incorrect."
        )
    elif response.status_code == helper.Response.FORBIDDEN:
        raise Exception(
            f"Error getting URL {url}. Status code: {response.status_code}. "
            "Make sure you have the read:statuses scope enabled for your access token."
        )
    else:
        raise Exception(
            f"Error getting URL {url}. Status code: {response.status_code}"
        )

def get_active_user_ids(server, access_token, reply_interval_hours):
    """get all user IDs on the server that have posted a toot in the given \
        time interval"""
    since = datetime.now() - timedelta(days=reply_interval_hours / 24 + 1)
    url = f"https://{server}/api/v1/admin/accounts"
    resp = helper.get(url, headers={
        "Authorization": f"Bearer {access_token}",
    })
    if resp.status_code == helper.Response.OK:
        for user in resp.json():
            last_status_at = user["account"]["last_status_at"]
            if last_status_at:
                last_active = datetime.strptime(last_status_at, "%Y-%m-%d")
                if last_active > since:
                    helper.log(f"Found active user: {user['username']}")
                    yield user["id"]
    elif resp.status_code == helper.Response.UNAUTHORIZED:
        raise Exception(
        f"Error getting user IDs on server {server}. Status code: {resp.status_code}. "
        "Ensure your access token is correct"
        )
    elif resp.status_code == helper.Response.FORBIDDEN:
        raise Exception(
        f"Error getting user IDs on server {server}. Status code: {resp.status_code}. "
    "Make sure you have the admin:read:accounts scope enabled for your access token."
        )
    else:
        raise Exception(
        f"Error getting user IDs on server {server}. Status code: {resp.status_code}"
        )

def get_all_reply_toots(
    server, user_ids, access_token, seen_urls, reply_interval_hours
):
    """get all replies to other users by the given users in the last day"""
    replies_since = datetime.now() - timedelta(hours=reply_interval_hours)
    reply_toots = list(
        itertools.chain.from_iterable(
            get_reply_toots(
                user_id, server, access_token, seen_urls, replies_since
            )
            for user_id in user_ids
        )
    )
    helper.log(f"Found {len(reply_toots)} reply toots")
    return reply_toots

def get_reply_toots(user_id, server, access_token, seen_urls, reply_since):
    """get replies by the user to other users since the given date"""
    url = f"https://{server}/api/v1/accounts/{user_id}/statuses?exclude_replies=false&limit=40"

    try:
        resp = helper.get(url, headers={
            "Authorization": f"Bearer {access_token}",
        })
    except Exception as ex:
        helper.log(
            f"Error getting replies for user {user_id} on server {server}: {ex}"
        )
        return []

    if resp.status_code == helper.Response.OK:
        toots = [
            toot
            for toot in resp.json()
            if toot["in_reply_to_id"]
            and toot["url"] not in seen_urls
            and datetime.strptime(toot["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
            > reply_since
        ]
        for toot in toots:
            helper.log(f"Found reply toot: {toot['url']}")
        return toots
    elif resp.status_code == helper.Response.FORBIDDEN:
        raise Exception(
            f"Error getting replies for user {user_id} on server {server}. \
Status code: {resp.status_code}. "
            "Make sure you have the read:statuses scope enabled for your access token."
        )

    raise Exception(
        f"Error getting replies for user {user_id} on server {server}. \
Status code: {resp.status_code}"
    )

def get_all_known_context_urls(server, reply_toots, parsed_urls):
    """get the context toots of the given toots from their original server"""
    known_context_urls = set()

    for toot in reply_toots:
        if toot_has_parseable_url(toot, parsed_urls):
            url = toot["url"] if toot["reblog"] is None else toot["reblog"]["url"]
            parsed_url = parse_url(url, parsed_urls)
            context = get_toot_context(parsed_url[0], parsed_url[1], url)
            if context:
                for item in context:
                    known_context_urls.add(item)
            else:
                helper.log(f"Error getting context for toot {url}")

    known_context_urls = set(filter(
        lambda url: not url.startswith(f"https://{server}/"), known_context_urls))
    helper.log(f"Found {len(known_context_urls)} known context toots")

    return known_context_urls

def get_all_replied_toot_server_ids(
    server, reply_toots, replied_toot_server_ids, parsed_urls
):
    """get the server and ID of the toots the given toots replied to"""
    return filter(
        lambda x: x is not None,
        (
        get_replied_toot_server_id(server, toot, replied_toot_server_ids, parsed_urls)
        for toot in reply_toots
        ),
    )

def get_replied_toot_server_id(server, toot, replied_toot_server_ids,parsed_urls):
    """get the server and ID of the toot the given toot replied to"""
    in_reply_to_id = toot["in_reply_to_id"]
    in_reply_to_account_id = toot["in_reply_to_account_id"]
    mentions = [
        mention
        for mention in toot["mentions"]
        if mention["id"] == in_reply_to_account_id
    ]
    if len(mentions) == 0:
        return None

    mention = mentions[0]

    o_url = f"https://{server}/@{mention['acct']}/{in_reply_to_id}"
    if o_url in replied_toot_server_ids:
        return replied_toot_server_ids[o_url]

    url = get_redirect_url(o_url)

    if url is None:
        return None

    match = parse_url(url,parsed_urls)
    if match:
        replied_toot_server_ids[o_url] = (url, match)
        return (url, match)

    helper.log(f"Error parsing toot URL {url}")
    replied_toot_server_ids[o_url] = None
    return None


def get_redirect_url(url):
    """get the URL given URL redirects to"""
    try:
        resp = requests.head(url, allow_redirects=False, timeout=5,headers={
            'User-Agent': 'FediFetcher (https://go.thms.uk/mgr)'
        })
    except Exception as ex:
        helper.log(f"Error getting redirect URL for URL {url}. Exception: {ex}")
        return None

    if resp.status_code == helper.Response.OK:
        return url
    elif resp.status_code == helper.Response.FOUND:
        redirect_url = resp.headers["Location"]
        helper.log(f"Discovered redirect for URL {url}")
        return redirect_url
    else:
        helper.log(
            f"Error getting redirect URL for URL {url}. Status code: {resp.status_code}"
        )
        return None


def get_all_context_urls(server, replied_toot_ids):
    """get the URLs of the context toots of the given toots"""
    return filter(
        lambda url: not url.startswith(f"https://{server}/"),
        itertools.chain.from_iterable(
            get_toot_context(server, toot_id, url)
            for (url, (server, toot_id)) in replied_toot_ids
        ),
    )


def get_toot_context(server, toot_id, toot_url):
    """get the URLs of the context toots of the given toot"""
    if toot_url.find("/comment/") != -1:
        return get_comment_context(server, toot_id, toot_url)
    if toot_url.find("/post/") != -1:
        return get_comments_urls(server, toot_id, toot_url)
    url = f"https://{server}/api/v1/statuses/{toot_id}/context"
    try:
        resp = helper.get(url)
    except Exception as ex:
        helper.log(f"Error getting context for toot {toot_url}. Exception: {ex}")
        return []

    if resp.status_code == helper.Response.OK:
        try:
            res = resp.json()
            helper.log(f"Got context for toot {toot_url}")
            return (toot["url"] for toot in (res["ancestors"] + res["descendants"]))
        except Exception as ex:
            helper.log(f"Error parsing context for toot {toot_url}. Exception: {ex}")
        return []
    elif resp.status_code == helper.Response.TOO_MANY_REQUESTS:
        reset = datetime.strptime(resp.headers['x-ratelimit-reset'],
            '%Y-%m-%dT%H:%M:%S.%fZ')
        helper.log(f"Rate Limit hit when getting context for {toot_url}. Waiting to retry at \
            {resp.headers['x-ratelimit-reset']}")
        time.sleep((reset - datetime.now()).total_seconds() + 1)
        return get_toot_context(server, toot_id, toot_url)

    helper.log(
        f"Error getting context for toot {toot_url}. Status code: {resp.status_code}"
    )
    return []

def get_comment_context(server, toot_id, toot_url):
    """get the URLs of the context toots of the given toot"""
    comment = f"https://{server}/api/v3/comment?id={toot_id}"
    try:
        resp = helper.get(comment)
    except Exception as ex:
        helper.log(f"Error getting comment {toot_id} from {toot_url}. Exception: {ex}")
        return []

    if resp.status_code == helper.Response.OK:
        try:
            res = resp.json()
            post_id = res['comment_view']['comment']['post_id']
            return get_comments_urls(server, post_id, toot_url)
        except Exception as ex:
            helper.log(f"Error parsing context for comment {toot_url}. Exception: {ex}")
        return []
    elif resp.status_code == helper.Response.TOO_MANY_REQUESTS:
        reset = datetime.strptime(resp.headers['x-ratelimit-reset'],
            '%Y-%m-%dT%H:%M:%S.%fZ')
        helper.log(f"Rate Limit hit when getting context for {toot_url}. Waiting to retry at \
            {resp.headers['x-ratelimit-reset']}")
        time.sleep((reset - datetime.now()).total_seconds() + 1)
        return get_comment_context(server, toot_id, toot_url)

def get_comments_urls(server, post_id, toot_url):
    """get the URLs of the comments of the given post"""
    urls = []
    url = f"https://{server}/api/v3/post?id={post_id}"
    try:
        resp = helper.get(url)
    except Exception as ex:
        helper.log(f"Error getting post {post_id} from {toot_url}. Exception: {ex}")
        return []

    if resp.status_code == helper.Response.OK:
        try:
            res = resp.json()
            if res['post_view']['counts']['comments'] == 0:
                return []
            urls.append(res['post_view']['post']['ap_id'])
        except Exception as ex:
            helper.log(f"Error parsing post {post_id} from {toot_url}. Exception: {ex}")

    url = f"https://{server}/api/v3/comment/list?post_id={post_id}&sort=New&limit=50"
    try:
        resp = helper.get(url)
    except Exception as ex:
        helper.log(f"Error getting comments for post {post_id} from {toot_url}. \
Exception: {ex}")
        return []

    if resp.status_code == helper.Response.OK:
        try:
            res = resp.json()
            list_of_urls = \
                [comment_info['comment']['ap_id'] for comment_info in res['comments']]
            helper.log(f"Got {len(list_of_urls)} comments for post {toot_url}")
            urls.extend(list_of_urls)
            return urls
        except Exception as ex:
            helper.log(f"Error parsing comments for post {toot_url}. Exception: {ex}")
    elif resp.status_code == helper.Response.TOO_MANY_REQUESTS:
        reset = datetime.strptime(resp.headers['x-ratelimit-reset'],
            '%Y-%m-%dT%H:%M:%S.%fZ')
        helper.log(f"Rate Limit hit when getting comments for {toot_url}. Waiting to retry at \
{resp.headers['x-ratelimit-reset']}")
        time.sleep((reset - datetime.now()).total_seconds() + 1)
        return get_comments_urls(server, post_id, toot_url)

    helper.log(f"Error getting comments for post {toot_url}. Status code: {resp.status_code}")
    return []

def get_paginated_mastodon(url, limit, headers = {}, timeout = 0, max_tries = 5):
    """Make a paginated request to mastodon"""
    if(isinstance(limit, int)):
        furl = f"{url}?limit={limit}"
    else:
        furl = url

    response = helper.get(furl, headers, timeout, max_tries)

    if response.status_code != helper.Response.OK:
        if response.status_code == helper.Response.UNAUTHORIZED:
            raise Exception(
                f"Error getting URL {url}. Status code: {response.status_code}. "
                "Ensure your access token is correct"
            )
        elif response.status_code == helper.Response.FORBIDDEN:
            raise Exception(
                f"Error getting URL {url}. Status code: {response.status_code}. "
                "Make sure you have the correct scopes enabled for your access token."
            )
        else:
            raise Exception(
                f"Error getting URL {url}. Status code: {response.status_code}"
            )

    result = response.json()

    if(isinstance(limit, int)):
        while len(result) < limit and 'next' in response.links:
            response = helper.get(response.links['next']['url'], headers, timeout, max_tries)
            result = result + response.json()
    else:
        while parser.parse(result[-1]['created_at']) >= limit \
                and 'next' in response.links:
            response = helper.get(response.links['next']['url'], headers, timeout, max_tries)
            result = result + response.json()

    return result

def filter_known_users(users, known_users):
    return list(filter(
        lambda user: user['acct'] not in known_users,
        users
    ))

def toot_has_parseable_url(toot,parsed_urls):
    parsed = parse_url(
        toot["url"] if toot["reblog"] is None else toot["reblog"]["url"], parsed_urls)
    if(parsed is None) :
        return False
    return True
