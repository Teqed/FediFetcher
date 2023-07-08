"""argparser.py - Parses command line arguments."""
import argparse
import json

argparser=argparse.ArgumentParser()

argparser.add_argument("-c","--config", required=False, type=str, help="Optionally \
    provide a path to a JSON file containing configuration options. If not provided, \
    options must be supplied using command line flags.")
argparser.add_argument("--server", required=False, help="Required: The name of \
    your server (e.g. `mstdn.thms.uk`)")
argparser.add_argument("--access-token", action="append", required=False,
    help="Required: The access token can be generated at \
    https://<server>/settings/applications, and must have read:search, read:statuses \
    and admin:read:accounts scopes. You can supply this multiple times, if you want to \
    run it for multiple users.")
argparser.add_argument("--reply-interval-in-hours", required = False, type=int,
    default=0, help="Fetch remote replies to posts that have received replies from \
    users on your own instance in this period")
argparser.add_argument("--home-timeline-length", required = False, type=int,
    default=0, help="Look for replies to posts in the API-Key owner's home \
    timeline, up to this many posts")
argparser.add_argument("--max-followings", required = False, type=int, default=0,
    help="Backfill posts for new accounts followed by --user. We'll backfill at \
    most this many followings' posts")
argparser.add_argument("--max-followers", required = False, type=int, default=0,
    help="Backfill posts for new accounts following --user. We'll backfill at most \
    this many followers' posts")
argparser.add_argument("--max-follow-requests", required = False, type=int, \
    default=0, help="Backfill posts of the API key owners pending follow requests. \
    We'll backfill at most this many requester's posts")
argparser.add_argument("--max-bookmarks", required = False, type=int, default=0,
    help="Fetch remote replies to the API key owners Bookmarks. We'll fetch \
    replies to at most this many bookmarks")
argparser.add_argument("--max-favourites", required = False, type=int, default=0,
    help="Fetch remote replies to the API key owners Favourites. We'll fetch \
    replies to at most this many favourites")
argparser.add_argument("--from-notifications", required = False, type=int,
    default=0, help="Backfill accounts of anyone appearing in your notifications, \
    during the last hours")
argparser.add_argument("--remember-users-for-hours", required=False, type=int,
    default=24*7, help="How long to remember users that you aren't following for, \
    before trying to backfill them again.")
argparser.add_argument("--http-timeout", required = False, type=int, default=5,
    help="The timeout for any HTTP requests to your own, or other instances.")
argparser.add_argument("--backfill-with-context", required = False, type=int,
    default=1, help="If enabled, we'll fetch remote replies when backfilling \
    profiles. Set to `0` to disable.")
argparser.add_argument("--backfill-mentioned-users", required = False, type=int,
    default=1, help="If enabled, we'll backfill any mentioned users when fetching \
    remote replies to timeline posts. Set to `0` to disable.")
argparser.add_argument("--lock-hours", required = False, type=int, default=24,
    help="The lock timeout in hours.")
argparser.add_argument("--lock-file", required = False, default=None,
    help="Location of the lock file")
argparser.add_argument("--state-dir", required = False, default="artifacts",
    help="Directory to store persistent files and possibly lock file")
argparser.add_argument("--on-done", required = False, default=None, help="Provide \
    a url that will be pinged when processing has completed. You can use this for \
    'dead man switch' monitoring of your task")
argparser.add_argument("--on-start", required = False, default=None, help="Provide \
    a url that will be pinged when processing is starting. You can use this for \
    'dead man switch' monitoring of your task")
argparser.add_argument("--on-fail", required = False, default=None, help="Provide \
    a url that will be pinged when processing has failed. You can use this for \
    'dead man switch' monitoring of your task")
argparser.add_argument("--log-level", required = False, type=int, default=20,
    help="Set the log level. 10=DEBUG, 20=INFO, 30=WARNING, 40=ERROR, 50=CRITICAL")
argparser.add_argument("--external-tokens", required = False, type=json.loads,
    default=None, help="Provide a JSON-formatted dictionary of external tokens, \
    keyed by server.")

arguments = argparser.parse_args()
