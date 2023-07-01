from datetime import datetime
import time
import helpers as helper

def add_context_url(url, server, access_token):
    """add the given toot URL to the server"""
    search_url = f"https://{server}/api/v2/search?q={url}&resolve=true&limit=1"

    try:
        resp = helper.get(search_url, headers={
            "Authorization": f"Bearer {access_token}",
        })
    except Exception as ex:
        helper.log(
            f"Error adding url {search_url} to server {server}. Exception: {ex}"
        )
        return False

    if resp.status_code == helper.Response.OK:
        helper.log(f"Added context url {url}")
        return True
    elif resp.status_code == helper.Response.FORBIDDEN:
        helper.log(
            f"Error adding url {search_url} to server {server}. \
Status code: {resp.status_code}. "
            "Make sure you have the read:search scope enabled for your access token."
        )
        return False
    elif resp.status_code == helper.Response.TOO_MANY_REQUESTS:
        reset = datetime.strptime(resp.headers['x-ratelimit-reset'],
            '%Y-%m-%dT%H:%M:%S.%fZ')
        helper.log(f"Rate Limit hit when adding url {search_url}. Waiting to retry at \
{resp.headers['x-ratelimit-reset']}")
        time.sleep((reset - datetime.now()).total_seconds() + 1)
        return add_context_url(url, server, access_token)
    else:
        helper.log(
            f"Error adding url {search_url} to server {server}. \
Status code: {resp.status_code}"
        )
        return False

def add_user_posts(server, access_token, followings, know_followings, all_known_users,
        seen_urls):
    for user in followings:
        if user['acct'] not in all_known_users and not user['url'].startswith(f"https://{server}/"):
            posts = get_user_posts(user, know_followings, server)

            if(posts is not None):
                count = 0
                failed = 0
                for post in posts:
                    if post.get('reblog') is None and post.get('url') and \
                            post.get('url') not in seen_urls:
                        added = add_post_with_context(
                            post, server, access_token, seen_urls)
                        if added is True:
                            seen_urls.add(post['url'])
                            count += 1
                        else:
                            failed += 1
                helper.log(f"Added {count} posts for user {user['acct']} with {failed} \
errors")
                if failed == 0:
                    know_followings.add(user['acct'])
                    all_known_users.add(user['acct'])

def add_post_with_context(post, server, access_token, seen_urls):
    added = add_context_url(post['url'], server, access_token)
    if added is True:
        seen_urls.add(post['url'])
        if ('replies_count' in post or 'in_reply_to_id' in post) and getattr(
                helper.arguments, 'backfill_with_context', 0) > 0:
            parsed_urls = {}
            parsed = parse_url(post['url'], parsed_urls)
            if parsed is None:
                return True
            known_context_urls = get_all_known_context_urls(server, [post],parsed_urls)
            add_context_urls(server, access_token, known_context_urls, seen_urls)
        return True

    return False

def add_context_urls(server, access_token, context_urls, seen_urls):
    """add the given toot URLs to the server"""
    count = 0
    failed = 0
    for url in context_urls:
        if url not in seen_urls:
            added = add_context_url(url, server, access_token)
            if added is True:
                seen_urls.add(url)
                count += 1
            else:
                failed += 1

    helper.log(f"Added {count} new context toots (with {failed} failures)")
