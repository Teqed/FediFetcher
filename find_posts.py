#!/usr/bin/env python3

import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta

from dateutil import parser

import fedifetcher.helpers as helper
from fedifetcher.ordered_set import OrderedSet

if __name__ == "__main__":
    start = datetime.now()

    helper.log("Starting FediFetcher")

    if(helper.arguments.config):
        if os.path.exists(helper.arguments.config):
            with open(helper.arguments.config, encoding="utf-8") as f:
                config = json.load(f)

            for key in config:
                setattr(helper.arguments, key.lower().replace("-","_"), config[key])

        else:
            helper.log(f"Config file {helper.arguments.config} doesn't exist")
            sys.exit(1)

    if(helper.arguments.server is None or helper.arguments.access_token is None):
        helper.log("You must supply at least a server name and an access token")
        sys.exit(1)

    # in case someone provided the server name as url instead,
    helper.arguments.server = re.sub("^(https://)?([^/]*)/?$", "\\2", helper.arguments.server)


    runId = uuid.uuid4()

    if(helper.arguments.on_start):
        try:
            helper.get(f"{helper.arguments.on_start}?rid={runId}")
        except Exception as ex:
            helper.log(f"Error getting callback url: {ex}")

    if helper.arguments.lock_file is None:
        helper.arguments.lock_file = os.path.join(helper.arguments.state_dir, "lock.lock")
    LOCK_FILE = helper.arguments.lock_file

    if( os.path.exists(LOCK_FILE)):
        helper.log(f"Lock file exists at {LOCK_FILE}")

        try:
            with open(LOCK_FILE, encoding="utf-8") as f:
                lock_time = parser.parse(f.read())

            if (datetime.now() - lock_time).total_seconds() >= \
                    helper.arguments.lock_hours * 60 * 60:
                os.remove(LOCK_FILE)
                helper.log("Lock file has expired. Removed lock file.")
            else:
                helper.log(f"Lock file age is {datetime.now() - lock_time} - \
below --lock-hours={helper.arguments.lock_hours} provided.")
                if(helper.arguments.on_fail):
                    try:
                        helper.get(f"{helper.arguments.on_fail}?rid={runId}")
                    except Exception as ex:
                        helper.log(f"Error getting callback url: {ex}")
                sys.exit(1)

        except Exception:
            helper.log("Cannot read logfile age - aborting.")
            if(helper.arguments.on_fail):
                try:
                    helper.get(f"{helper.arguments.on_fail}?rid={runId}")
                except Exception as ex:
                    helper.log(f"Error getting callback url: {ex}")
            sys.exit(1)

    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        f.write(f"{datetime.now()}")

    try:

        SEEN_URLS_FILE = os.path.join(helper.arguments.state_dir, "seen_urls")
        REPLIED_TOOT_SERVER_IDS_FILE = os.path.join(
            helper.arguments.state_dir, "replied_toot_server_ids")
        KNOWN_FOLLOWINGS_FILE = os.path.join(helper.arguments.state_dir, "known_followings")
        RECENTLY_CHECKED_USERS_FILE = os.path.join(
            helper.arguments.state_dir, "recently_checked_users")


        seen_urls = OrderedSet([])
        if os.path.exists(SEEN_URLS_FILE):
            with open(SEEN_URLS_FILE, encoding="utf-8") as f:
                seen_urls = OrderedSet(f.read().splitlines())

        replied_toot_server_ids = {}
        if os.path.exists(REPLIED_TOOT_SERVER_IDS_FILE):
            with open(REPLIED_TOOT_SERVER_IDS_FILE, encoding="utf-8") as f:
                replied_toot_server_ids = json.load(f)

        known_followings = OrderedSet([])
        if os.path.exists(KNOWN_FOLLOWINGS_FILE):
            with open(KNOWN_FOLLOWINGS_FILE, encoding="utf-8") as f:
                known_followings = OrderedSet(f.read().splitlines())

        recently_checked_users = OrderedSet({})
        if os.path.exists(RECENTLY_CHECKED_USERS_FILE):
            with open(RECENTLY_CHECKED_USERS_FILE, encoding="utf-8") as f:
                recently_checked_users = OrderedSet(json.load(f))

        # Remove any users whose last check is too long in the past from the list
        for user in list(recently_checked_users):
            lastCheck = recently_checked_users.get(user)
            userAge = datetime.now(lastCheck.tzinfo) - lastCheck
            if(userAge.total_seconds() > helper.arguments.remember_users_for_hours * 60 * 60):
                recently_checked_users.pop(user)

        parsed_urls = {}

        all_known_users = OrderedSet(
            list(known_followings) + list(recently_checked_users))

        if(isinstance(helper.arguments.access_token, str)):
            helper.arguments.access_token = [helper.arguments.access_token]

        for token in helper.arguments.access_token:

            if helper.arguments.reply_interval_in_hours > 0:
                """pull the context toots of toots user replied to, from their
                original server, and add them to the local server."""
                user_ids = get_active_user_ids(
                    helper.arguments.server, token, helper.arguments.reply_interval_in_hours)
                reply_toots = get_all_reply_toots(
                    helper.arguments.server, user_ids, token,
                    seen_urls, helper.arguments.reply_interval_in_hours,
                )
                known_context_urls = get_all_known_context_urls(
                    helper.arguments.server, reply_toots,parsed_urls)
                seen_urls.update(known_context_urls)
                replied_toot_ids = get_all_replied_toot_server_ids(
                    helper.arguments.server, reply_toots, replied_toot_server_ids, parsed_urls,
                )
                context_urls = get_all_context_urls(helper.arguments.server, replied_toot_ids)
                add_context_urls(helper.arguments.server, token, context_urls, seen_urls)


            if helper.arguments.home_timeline_length > 0:
                """Do the same with any toots on the key owner's home timeline """
                timeline_toots = get_timeline(
                    helper.arguments.server, token, helper.arguments.home_timeline_length)
                known_context_urls = get_all_known_context_urls(
                    helper.arguments.server, timeline_toots,parsed_urls)
                add_context_urls(helper.arguments.server, token, known_context_urls, seen_urls)

                # Backfill any post authors, and any mentioned users
                if helper.arguments.backfill_mentioned_users > 0:
                    mentioned_users = []
                    cut_off = datetime.now(
                        datetime.now().astimezone().tzinfo) - timedelta(minutes=60)
                    for toot in timeline_toots:
                        these_users = []
                        toot_created_at = parser.parse(toot["created_at"])
                        if len(mentioned_users) < 10 or (
                                toot_created_at > cut_off and \
                                    len(mentioned_users) < 30):
                            these_users.append(toot["account"])
                            if(len(toot["mentions"])):
                                these_users += toot["mentions"]
                            if(toot["reblog"]):
                                these_users.append(toot["reblog"]["account"])
                                if(len(toot["reblog"]["mentions"])):
                                    these_users += toot["reblog"]["mentions"]
                        for user in these_users:
                            if user not in mentioned_users and \
                                    user["acct"] not in all_known_users:
                                mentioned_users.append(user)

                    add_user_posts(helper.arguments.server, token, filter_known_users(
                        mentioned_users, all_known_users), recently_checked_users,
                        all_known_users, seen_urls)

            if helper.arguments.max_followings > 0:
                helper.log(f"Getting posts from last {helper.arguments.max_followings} followings")
                user_id = get_user_id(helper.arguments.server, helper.arguments.user, token)
                followings = get_new_followings(helper.arguments.server, user_id,
                                            helper.arguments.max_followings, all_known_users)
                add_user_posts(helper.arguments.server, token, followings, known_followings,
                                            all_known_users, seen_urls)

            if helper.arguments.max_followers > 0:
                helper.log(f"Getting posts from last {helper.arguments.max_followers} followers")
                user_id = get_user_id(helper.arguments.server, helper.arguments.user, token)
                followers = get_new_followers(helper.arguments.server, user_id,
                                            helper.arguments.max_followers, all_known_users)
                add_user_posts(helper.arguments.server, token, followers,
                            recently_checked_users, all_known_users, seen_urls)

            if helper.arguments.max_follow_requests > 0:
                helper.log(f"Getting posts from last {helper.arguments.max_follow_requests} \
follow requests")
                follow_requests = get_new_follow_requests(helper.arguments.server, token,
                                        helper.arguments.max_follow_requests, all_known_users)
                add_user_posts(helper.arguments.server, token, follow_requests,
                                recently_checked_users, all_known_users, seen_urls)

            if helper.arguments.from_notifications > 0:
                helper.log(f"Getting notifications for last {helper.arguments.from_notifications} \
hours")
                notification_users = get_notification_users(helper.arguments.server, token,
                                        all_known_users, helper.arguments.from_notifications)
                add_user_posts(helper.arguments.server, token, notification_users,
                            recently_checked_users, all_known_users, seen_urls)

            if helper.arguments.max_bookmarks > 0:
                helper.log(f"Pulling replies to the last {helper.arguments.max_bookmarks} bookmarks")
                bookmarks = get_bookmarks(
                    helper.arguments.server, token, helper.arguments.max_bookmarks)
                known_context_urls = get_all_known_context_urls(
                    helper.arguments.server, bookmarks,parsed_urls)
                add_context_urls(helper.arguments.server, token, known_context_urls, seen_urls)

            if helper.arguments.max_favourites > 0:
                helper.log(f"Pulling replies to the last {helper.arguments.max_favourites} \
favourites")
                favourites = get_favourites(
                    helper.arguments.server, token, helper.arguments.max_favourites)
                known_context_urls = get_all_known_context_urls(
                    helper.arguments.server, favourites,parsed_urls)
                add_context_urls(helper.arguments.server, token, known_context_urls, seen_urls)

        with open(KNOWN_FOLLOWINGS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(list(known_followings)[-10000:]))

        with open(SEEN_URLS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(list(seen_urls)[-10000:]))

        with open(REPLIED_TOOT_SERVER_IDS_FILE, "w", encoding="utf-8") as f:
            json.dump(dict(list(replied_toot_server_ids.items())[-10000:]), f)

        with open(RECENTLY_CHECKED_USERS_FILE, "w", encoding="utf-8") as f:
            recently_checked_users.toJSON()

        os.remove(LOCK_FILE)

        if(helper.arguments.on_done):
            try:
                helper.get(f"{helper.arguments.on_done}?rid={runId}")
            except Exception as ex:
                helper.log(f"Error getting callback url: {ex}")

        helper.log(f"Processing finished in {datetime.now() - start}.")

    except Exception:
        os.remove(LOCK_FILE)
        helper.log(f"Job failed after {datetime.now() - start}.")
        if(helper.arguments.on_fail):
            try:
                helper.get(f"{helper.arguments.on_fail}?rid={runId}")
            except Exception as ex:
                helper.log(f"Error getting callback url: {ex}")
        raise
