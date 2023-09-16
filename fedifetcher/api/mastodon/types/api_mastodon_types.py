"""Mastodon types."""
from __future__ import annotations  # python< 3.9 compat

from datetime import datetime  # noqa: TCH003

from .api_mastodon_types_base import (
    AttribAccessDict,
    EntityList,
    IdType,
    MaybeSnowflakeIdType,
)


class Account(AttribAccessDict):
    """A user acccount, local or remote.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Account/
    """

    id: MaybeSnowflakeIdType
    """
    The accounts id.
    """

    username: str
    """
    The username, without the domain part.
    """

    acct: str
    """
    The user's account name as username@domain (@domain omitted for local users).
    """

    display_name: str
    """
    The user's display name.
    """

    discoverable: bool | None
    """
    Indicates whether or not a user is visible on the discovery page. (nullable)
    """

    group: bool
    """
    A boolean indicating whether the account represents a group rather than an individual.
    """

    locked: bool
    """
    Denotes whether the account can be followed without a follow request.
    """

    created_at: datetime
    """
    The accounts creation time.
      * 3.4.0: now resolves to midnight instead of an exact time
    """

    following_count: int
    """
    How many accounts this account follows.
    """

    followers_count: int
    """
    How many followers this account has.
    """

    statuses_count: int
    """
    How many statuses this account has created, excluding: 1) later deleted posts 2) direct messages / 'mentined users only' posts, except in earlier versions mastodon.
      * 2.4.2: no longer includes direct / mentioned-only visibility statuses
    """

    note: str
    """
    The users bio / profile text / 'note'.
    """

    url: str
    """
    A URL pointing to this users profile page (can be remote).
    Should contain (as text): URL
    """

    avatar: str
    """
    URL for this users avatar, can be animated.
    Should contain (as text): URL
    """

    header: str
    """
    URL for this users header image, can be animated.
    Should contain (as text): URL
    """

    avatar_static: str
    """
    URL for this users avatar, never animated.
    Should contain (as text): URL
    """

    header_static: str
    """
    URL for this users header image, never animated.
    Should contain (as text): URL
    """

    moved_to_account: Account | None
    """
    If set, Account that this user has set up as their moved-to address. (optional)
    """

    suspended: bool | None
    """
    Boolean indicating whether the user has been suspended. (optional)
    """

    limited: bool | None
    """
    Boolean indicating whether the user has been silenced. (optional)
    """

    bot: bool
    """
    Boolean indicating whether this account is automated.
    """

    fields: EntityList[AccountField]
    """
    List of up to four (by default) AccountFields.
    """

    emojis: EntityList[CustomEmoji]
    """
    List of custom emoji used in name, bio or fields.
    """

    last_status_at: datetime | None
    """
    When the most recent status was posted. (nullable)
    """

    noindex: bool | None
    """
    Whether the local user has opted out of being indexed by search engines. (nullable)
    """

    roles: EntityList
    """
    THIS FIELD IS DEPRECATED. IT IS RECOMMENDED THAT YOU DO NOT USE IT.
    """

    role: Role | None
    """
    The users role. Only present for account returned from account_verify_credentials(). (optional)
    """

    source: CredentialAccountSource | None
    """
    Additional information about the account, useful for profile editing. Only present for account returned from account_verify_credentials(). (optional)
    """

    mute_expires_at: datetime | None
    """
    If the user is muted by the logged in user with a timed mute, when the mute expires. (nullable)
    """

    _version = "4.0.0"

class AccountField(AttribAccessDict):
    """A field, displayed on a users profile (e.g. "Pronouns", "Favorite color").

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Account/
    """

    name: str
    """
    The key of a given field's key-value pair.
    """

    value: str
    """
    The value associated with the `name` key.
    """

    verified_at: str | None
    """
    Timestamp of when the server verified a URL value for a rel="me" link. (nullable)
    """

    _version = "2.6.0"

class Role(AttribAccessDict):
    """A role granting a user a set of permissions.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Role/
    """

    id: IdType
    """
    The ID of the Role in the database.
    """

    name: str
    """
    The name of the role.
    """

    permissions: str
    """
    A bitmask that represents the sum of all permissions granted to the role.
    """

    color: str
    """
    The hex code assigned to this role. If no hex code is assigned, the string will be empty.
    """

    highlighted: bool
    """
    Whether the role is publicly visible as a badge on user profiles.
    """

    _version = "4.0.0"

class CredentialAccountSource(AttribAccessDict):
    """Source values useful for editing a user's profile.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Account/
    """

    privacy: str
    """
    The user's default visibility setting ("private", "unlisted" or "public").
    """

    sensitive: bool
    """
    Denotes whether user media should be marked sensitive by default.
    """

    note: str
    """
    Plain text version of the user's bio.
    """

    language: str
    """
    The default posting language for new statuses.
    Should contain (as text): TwoLetterLanguageCodeEnum
    """

    fields: EntityList[AccountField]
    """
    Metadata about the account.
    """

    follow_requests_count: int
    """
    The number of pending follow requests.
    """

    _version = "3.0.0"

class Status(AttribAccessDict):
    """A single status / toot / post.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Status/
    """

    id: MaybeSnowflakeIdType
    """
    Id of this status.
    """

    uri: str
    """
    Descriptor for the status. Mastodon, for example, may use something like: 'tag:mastodon.social,2016-11-25:objectId=<id>:objectType=Status'.
    """

    url: str | None
    """
    URL of the status. (nullable)
    Should contain (as text): URL
    """

    account: Account
    """
    Account which posted the status.
    """

    in_reply_to_id: MaybeSnowflakeIdType | None
    """
    Id of the status this status is in response to. (nullable)
    """

    in_reply_to_account_id: MaybeSnowflakeIdType | None
    """
    Id of the account this status is in response to. (nullable)
    """

    reblog: Status | None
    """
    Denotes whether the status is a reblog. If so, set to the original status. (nullable)
    """

    content: str
    """
    Content of the status, as HTML: '<p>Hello from Python</p>'.
    Should contain (as text): HTML
    """

    created_at: datetime
    """
    Creation time.
    """

    reblogs_count: int
    """
    Number of reblogs.
    """

    favourites_count: int
    """
    Number of favourites.
    """

    reblogged: bool | None
    """
    Denotes whether the logged in user has boosted this status. (optional)
    """

    favourited: bool | None
    """
    Denotes whether the logged in user has favourited this status. (optional)
    """

    sensitive: bool
    """
    Denotes whether media attachments to the status are marked sensitive.
    """

    spoiler_text: str
    """
    Warning text that should be displayed before the status content.
    """

    visibility: str
    """
    Toot visibility.
    Should contain (as text): VisibilityEnum
    """

    mentions: EntityList[Account]
    """
    A list Mentions this status includes.
    """

    media_attachments: EntityList[MediaAttachment]
    """
    List files attached to this status.
    """

    emojis: EntityList[CustomEmoji]
    """
    A list of CustomEmoji used in the status.
    """

    tags: EntityList[Tag]
    """
    A list of Tags used in the status.
    """

    bookmarked: bool | None
    """
    True if the status is bookmarked by the logged in user, False if not. (optional)
    """

    application: Application | None
    """
    Application for the client used to post the status (Does not federate and is therefore always None for remote statuses, can also be None for local statuses for some legacy applications registered before this field was introduced). (optional)
    """

    language: str | None
    """
    The language of the status, if specified by the server, as ISO 639-1 (two-letter) language code. (nullable)
    Should contain (as text): TwoLetterLanguageCodeEnum
    """

    muted: bool | None
    """
    Boolean denoting whether the user has muted this status by way of conversation muting. (optional)
    """

    pinned: bool | None
    """
    Boolean denoting whether or not the status is currently pinned for the associated account. (optional)
    """

    replies_count: int
    """
    The number of replies to this status.
    """

    card: PreviewCard | None
    """
    A preview card for links from the status, if present at time of delivery. (nullable)
    """

    poll: Poll | None
    """
    A poll object if a poll is attached to this status. (nullable)
    """

    edited_at: datetime | None
    """
    Time the status was last edited. (nullable)
    """

    filtered: EntityList[FilterResult] | None
    """
    If present, a list of filter application results that indicate which of the users filters matched and what actions should be taken. (optional)
    """

    _version = "4.0.0"

class StatusEdit(AttribAccessDict):
    """An object representing a past version of an edited status.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/StatusEdit/
    """

    content: str
    """
    Content for this version of the status.
    """

    spoiler_text: str
    """
    CW / Spoiler text for this version of the status.
    """

    sensitive: bool
    """
    Whether media in this version of the status is marked as sensitive.
    """

    created_at: datetime
    """
    Time at which this version of the status was posted.
    """

    account: Account
    """
    Account object of the user that posted the status.
    """

    media_attachments: EntityList[MediaAttachment]
    """
    List of MediaAttachment objects with the attached media for this version of the status.
    """

    emojis: EntityList[CustomEmoji]
    """
    List of custom emoji used in this version of the status.
    """

    poll: Poll
    """
    The current state of the poll options at this revision. Note that edits changing the poll options will be collapsed together into one edit, since this action resets the poll.
    """

    _version = "3.5.0"

class FilterResult(AttribAccessDict):
    """A filter action that should be taken on a status.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/FilterResult/
    """

    filter: Filter | FilterV2
    """
    The filter that was matched.
    """

    keyword_matches: EntityList[str] | None
    """
    The keyword within the filter that was matched. (nullable)
    """

    status_matches: EntityList | None
    """
    The status ID within the filter that was matched. (nullable)
    """

    _version = "4.0.0"

class StatusMention(AttribAccessDict):
    """A mention of a user within a status.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Mention/
    """

    url: str
    """
    Mentioned user's profile URL (potentially remote).
    Should contain (as text): URL
    """

    username: str
    """
    Mentioned user's user name (not including domain).
    """

    acct: str
    """
    Mentioned user's account name (including domain).
    """

    id: IdType
    """
    Mentioned user's (local) account ID.
    """

    _version = "0.6.0"

class ScheduledStatus(AttribAccessDict):
    """A scheduled status / toot to be eventually posted.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/ScheduledStatus/
    """

    id: IdType
    """
    Scheduled status ID (note: Not the id of the status once it gets posted!).
    """

    scheduled_at: datetime
    """
    datetime object describing when the status is to be posted.
    """

    params: ScheduledStatusParams
    """
    Parameters for the scheduled status, specifically.
    """

    media_attachments: EntityList
    """
    Array of MediaAttachment objects for the attachments to the scheduled status.
    """

    _version = "2.7.0"

class ScheduledStatusParams(AttribAccessDict):
    """Parameters for a status / toot to be posted in the future.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/ScheduledStatus/
    """

    text: str
    """
    Toot text.
    """

    in_reply_to_id: MaybeSnowflakeIdType | None
    """
    ID of the status this one is a reply to. (nullable)
    """

    media_ids: EntityList[str] | None
    """
    IDs of media attached to this status. (nullable)
    """

    sensitive: bool | None
    """
    Whether this status is sensitive or not. (nullable)
    """

    visibility: str
    """
    Visibility of the status.
    """

    idempotency: str | None
    """
    Idempotency key for the scheduled status. (nullable)
    """

    scheduled_at: datetime | None
    """
    Present, but generally "None". Unsure what this is for - the actual scheduled_at is in the ScheduledStatus object, not here. If you know, let me know. (nullable)
    """

    spoiler_text: str | None
    """
    CW text for this status. (nullable)
    """

    application_id: IdType
    """
    ID of the application that scheduled the status.
    """

    poll: Poll | None
    """
    Poll parameters. (nullable)
    """

    language: str | None
    """
    The language that will be used for the status. (nullable)
    Should contain (as text): TwoLetterLanguageCodeEnum
    """

    allowed_mentions: EntityList[str] | None
    """
    Undocumented. If you know what this does, please let me know. (nullable)
    """

    with_rate_limit: bool
    """
    Whether the status should be rate limited. It is unclear to me what this does. If you know, please let met know.
    """

    _version = "2.8.0"

class Poll(AttribAccessDict):
    """A poll attached to a status.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Poll/
    """

    id: IdType
    """
    The polls ID.
    """

    expires_at: datetime | None
    """
    The time at which the poll is set to expire. (nullable)
    """

    expired: bool
    """
    Boolean denoting whether users can still vote in this poll.
    """

    multiple: bool
    """
    Boolean indicating whether it is allowed to vote for more than one option.
    """

    votes_count: int
    """
    Total number of votes cast in this poll.
    """

    voted: bool
    """
    Boolean indicating whether the logged-in user has already voted in this poll.
    """

    options: EntityList[PollOption]
    """
    The poll options.
    """

    emojis: EntityList[CustomEmoji]
    """
    List of CustomEmoji used in answer strings,.
    """

    own_votes: EntityList[int]
    """
    The logged-in users votes, as a list of indices to the options.
    """

    voters_count: int | None
    """
    How many unique accounts have voted on a multiple-choice poll. (nullable)
    """

    _version = "2.8.0"

class PollOption(AttribAccessDict):
    """A poll option within a poll.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Poll/
    """

    title: str
    """
    Text of the option.
    """

    votes_count: int | None
    """
    Count of votes for the option. Can be None if the poll creator has chosen to hide vote totals until the poll expires and it hasn't yet. (nullable)
    """

    _version = "2.8.0"

class Conversation(AttribAccessDict):
    """A conversation (using direct / mentions-only visibility) between two or more users.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Conversation/
    """

    id: IdType
    """
    The ID of this conversation object.
    """

    unread: bool
    """
    Boolean indicating whether this conversation has yet to be read by the user.
    """

    accounts: EntityList[Account]
    """
    List of accounts (other than the logged-in account) that are part of this conversation.
    """

    last_status: Status | None
    """
    The newest status in this conversation. (nullable)
    """

    _version = "2.6.0"

class Tag(AttribAccessDict):
    """A hashtag, as part of a status or on its own (e.g. trending).

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Tag/
    """

    name: str
    """
    Hashtag name (not including the #).
    """

    url: str
    """
    Hashtag URL (can be remote).
    Should contain (as text): URL
    """

    history: EntityList[TagHistory] | None
    """
    List of TagHistory for up to 7 days. Not present in statuses. (optional)
    """

    following: bool | None
    """
    Boolean indicating whether the logged-in user is following this tag. (optional)
    """

    _version = "4.0.0"

class TagHistory(AttribAccessDict):
    """Usage history for a hashtag.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Tag/
    """

    day: datetime
    """
    Date of the day this TagHistory is for.
    Should contain (as text): datetime
    """

    uses: str
    """
    Number of statuses using this hashtag on that day.
    """

    accounts: str
    """
    Number of accounts using this hashtag in at least one status on that day.
    """

    _version = "2.4.1"

class CustomEmoji(AttribAccessDict):
    """A custom emoji.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/CustomEmoji/
    """

    shortcode: str
    """
    Emoji shortcode, without surrounding colons.
    """

    url: str
    """
    URL for the emoji image, can be animated.
    Should contain (as text): URL
    """

    static_url: str
    """
    URL for the emoji image, never animated.
    Should contain (as text): URL
    """

    visible_in_picker: bool
    """
    True if the emoji is enabled, False if not.
    """

    category: str
    """
    The category to display the emoji under (not present if none is set).
    """

    _version = "3.0.0"

class Application(AttribAccessDict):
    """Information about an app (in terms of the API).

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Application/
    """

    name: str
    """
    The applications name.
    """

    website: str | None
    """
    The applications website. (nullable)
      * 3.5.1: this property is now nullable
    """

    vapid_key: str
    """
    A vapid key that can be used in web applications.
    """

    _version = "3.5.1"

class Relationship(AttribAccessDict):
    """Information about the relationship between two users.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Relationship/
    """

    id: IdType
    """
    ID of the relationship object.
    """

    following: bool
    """
    Boolean denoting whether the logged-in user follows the specified user.
    """

    followed_by: bool
    """
    Boolean denoting whether the specified user follows the logged-in user.
    """

    blocking: bool
    """
    Boolean denoting whether the logged-in user has blocked the specified user.
    """

    blocked_by: bool
    """
    Boolean denoting whether the logged-in user has been blocked by the specified user, if information is available.
    """

    muting: bool
    """
    Boolean denoting whether the logged-in user has muted the specified user.
    """

    muting_notifications: bool
    """
    Boolean denoting wheter the logged-in user has muted notifications related to the specified user.
    """

    requested: bool
    """
    Boolean denoting whether the logged-in user has sent the specified user a follow request.
    """

    domain_blocking: bool
    """
    Boolean denoting whether the logged-in user has blocked the specified users domain.
    """

    showing_reblogs: bool
    """
    Boolean denoting whether the specified users reblogs show up on the logged-in users Timeline.
    """

    endorsed: bool
    """
    Boolean denoting wheter the specified user is being endorsed / featured by the logged-in user.
    """

    note: str
    """
    A free text note the logged in user has created for this account (not publicly visible).
    """

    notifying: bool
    """
    Boolean indicating whether the logged-in user has enabled notifications for this users posts.
    """

    languages: EntityList[str] | None
    """
    List of languages that the logged in user is following this user for (if any). (nullable)
    Should contain (as text): TwoLetterLanguageCodeEnum
    """

    requested_by: bool
    """
    Boolean indicating whether the specified user has sent the logged-in user a follow request.
    """

    _version = "4.0.0"

class Filter(AttribAccessDict):
    """Information about a keyword / status filter.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/V1_Filter/
    """

    id: IdType
    """
    Id of the filter.
    """

    phrase: str
    """
    Filtered keyword or phrase.
    """

    context: EntityList[str]
    """
    List of places where the filters are applied.
    Should contain (as text): FilterContextEnum
      * 3.1.0: added `account`
    """

    expires_at: datetime | None
    """
    Expiry date for the filter. (nullable)
    """

    irreversible: bool
    """
    Boolean denoting if this filter is executed server-side or if it should be ran client-side.
    """

    whole_word: bool
    """
    Boolean denoting whether this filter can match partial words.
    """

    _version = "3.1.0"

class FilterV2(AttribAccessDict):
    """Information about a keyword / status filter.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Filter/
    """

    id: IdType
    """
    Id of the filter.
    """

    context: EntityList[str]
    """
    List of places where the filters are applied.
    Should contain (as text): FilterContextEnum
    """

    expires_at: datetime | None
    """
    Expiry date for the filter. (nullable)
    """

    title: str
    """
    Name the user has chosen for this filter.
    """

    filter_action: str
    """
    The action to be taken when a status matches this filter.
    Should contain (as text): FilterActionEnum
    """

    keywords: EntityList[FilterKeyword]
    """
    A list of keywords that will trigger this filter.
    """

    statuses: EntityList[FilterStatus]
    """
    A list of statuses that will trigger this filter.
    """

    _version = "4.0.0"

class Notification(AttribAccessDict):
    """A notification about some event, like a new reply or follower.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Notification/
    """

    id: IdType
    """
    id of the notification.
    """

    type: str
    """
    "mention", "reblog", "favourite", "follow", "poll" or "follow_request".
    Should contain (as text): NotificationTypeEnum
      * 2.8.0: added `poll`
      * 3.1.0: added `follow_request`
      * 3.3.0: added `status`
      * 3.5.0: added `update` and `admin.sign_up`
      * 4.0.0: added `admin.report`
    """

    created_at: datetime
    """
    The time the notification was created.
    """

    account: Account
    """
    Account of the user from whom the notification originates.
    """

    status: Status
    """
    In case of "mention", the mentioning status In case of reblog / favourite, the reblogged / favourited status.
    """

    _version = "4.0.0"

class Context(AttribAccessDict):
    """The conversation context for a given status, i.e. its predecessors (that it replies to) and successors (that reply to it).

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Context/
    """

    ancestors: EntityList[Status]
    """
    A list of Statuses that the Status with this Context is a reply to.
    """

    descendants: EntityList[Status]
    """
    A list of Statuses that are replies to the Status with this Context.
    """

    _version = "0.6.0"

class UserList(AttribAccessDict):
    """A list of users.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/List/
    """

    id: IdType
    """
    id of the list.
    """

    title: str
    """
    title of the list.
    """

    replies_policy: str
    """
    Which replies should be shown in the list.
    Should contain (as text): RepliesPolicyEnum
    """

    _version = "3.3.0"

class MediaAttachment(AttribAccessDict):
    """A piece of media (like an image, video, or audio file) that can be or has been attached to a status.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/MediaAttachment/
    """

    id: MaybeSnowflakeIdType
    """
    The ID of the attachment.
    """

    type: str
    """
    Media type: 'image', 'video', 'gifv', 'audio' or 'unknown'.
      * 2.9.1: added `audio`
    """

    url: str
    """
    The URL for the image in the local cache.
    Should contain (as text): URL
    """

    remote_url: str | None
    """
    The remote URL for the media (if the image is from a remote instance). (nullable)
    Should contain (as text): URL
    """

    preview_url: str
    """
    The URL for the media preview.
    Should contain (as text): URL
    """

    text_url: str
    """
    THIS FIELD IS DEPRECATED. IT IS RECOMMENDED THAT YOU DO NOT USE IT.

    Deprecated. The display text for the media (what shows up in text). May not be present in mastodon versions after 3.5.0.
    Should contain (as text): URL
      * 3.5.0: removed
    """

    meta: MediaAttachmentMetadataContainer
    """
    MediaAttachmentMetadataContainer that contains metadata for 'original' and 'small' (preview) versions of the MediaAttachment. Either may be empty. May additionally contain an "fps" field giving a videos frames per second (possibly rounded), and a "length" field giving a videos length in a human-readable format. Note that a video may have an image as preview. May also contain a 'focus' object and a media 'colors' object.
      * 2.3.0: added focus
      * 4.0.0: added colors
    """

    blurhash: str
    """
    The blurhash for the image, used for preview / placeholder generation.
    Should contain (as text): Blurhash
    """

    description: str | None
    """
    If set, the user-provided description for this media. (nullable)
    """

    preview_remote_url: str | None
    """
    If set, the remote URL for the thumbnail of this media attachment on the or originating instance. (nullable)
    Should contain (as text): URL
    """

    _version = "4.0.0"

class MediaAttachmentMetadataContainer(AttribAccessDict):
    """An object holding metadata about a media attachment and its thumbnail.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/MediaAttachment/
    """

    original: MediaAttachmentImageMetadata | MediaAttachmentVideoMetadata | MediaAttachmentAudioMetadata
    """
    Metadata for the original media attachment.
    """

    small: MediaAttachmentImageMetadata
    """
    Metadata for the thumbnail of this media attachment.
    """

    colors: MediaAttachmentColors
    """
    Information about accent colors for the media.
    """

    focus: MediaAttachmentFocusPoint
    """
    Information about the focus point for the media.
    """

    _version = "4.0.0"

class MediaAttachmentImageMetadata(AttribAccessDict):
    """Metadata for an image media attachment.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/MediaAttachment/
    """

    width: int
    """
    Width of the image in pixels.
    """

    height: int
    """
    Height of the image in pixels.
    """

    aspect: float
    """
    Aspect ratio of the image as a floating point number.
    """

    size: str
    """
    Textual representation of the image size in pixels, e.g. '800x600'.
    """

    _version = "0.6.0"

class MediaAttachmentVideoMetadata(AttribAccessDict):
    """Metadata for a video or gifv media attachment.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/MediaAttachment/
    """

    width: int
    """
    Width of the video in pixels.
    """

    height: int
    """
    Height of the video in pixels.
    """

    frame_rate: str
    """
    Exact frame rate of the video in frames per second. Can be an integer fraction (i.e. "20/7").
    """

    duration: float
    """
    Duration of the video in seconds.
    """

    bitrate: int
    """
    Average bit-rate of the video in bytes per second.
    """

    _version = "0.6.0"

class MediaAttachmentAudioMetadata(AttribAccessDict):
    """Metadata for an audio media attachment.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/MediaAttachment/
    """

    duration: float
    """
    Duration of the audio file in seconds.
    """

    bitrate: int
    """
    Average bit-rate of the audio file in bytes per second.
    """

    _version = "0.6.0"

class MediaAttachmentFocusPoint(AttribAccessDict):
    """The focus point for a media attachment, for cropping purposes.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/MediaAttachment/
    """

    x: float
    """
    Focus point x coordinate (between -1 and 1), with 0 being the center and -1 and 1 being the left and right edges respectively.
    """

    y: float
    """
    Focus point x coordinate (between -1 and 1), with 0 being the center and -1 and 1 being the upper and lower edges respectively.
    """

    _version = "2.3.0"

class MediaAttachmentColors(AttribAccessDict):
    """Object describing the accent colors for a media attachment.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/MediaAttachment/
    """

    foreground: str
    """
    Estimated foreground colour for the attachment thumbnail, as a html format hex color (#rrggbb).
    """

    background: str
    """
    Estimated background colour for the attachment thumbnail, as a html format hex color (#rrggbb).
    """

    accent: str
    """
    Estimated accent colour for the attachment thumbnail.
    """

    _version = "4.0.0"

class PreviewCard(AttribAccessDict):
    """A preview card attached to a status, e.g. for an embedded video or link.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/PreviewCard/
    """

    url: str
    """
    The URL of the card.
    Should contain (as text): URL
    """

    title: str
    """
    The title of the card.
    """

    description: str
    """
    Description of the embedded content.
    """

    type: str
    """
    Embed type: 'link', 'photo', 'video', or 'rich'.
    """

    image: str | None
    """
    (optional) The image associated with the card. (nullable)
    Should contain (as text): URL
    """

    author_name: str
    """
    Name of the embedded contents author.
    """

    author_url: str
    """
    URL pointing to the embedded contents author.
    Should contain (as text): URL
    """

    width: int
    """
    Width of the embedded object.
    """

    height: int
    """
    Height of the embedded object.
    """

    html: str
    """
    HTML string representing the embed.
    Should contain (as text): HTML
    """

    provider_name: str
    """
    Name of the provider from which the embed originates.
    """

    provider_url: str
    """
    URL pointing to the embeds provider.
    Should contain (as text): URL
    """

    blurhash: str | None
    """
    Blurhash of the preview image. (nullable)
    Should contain (as text): Blurhash
    """

    language: str | None
    """
    Language of the embedded content. (optional)
    Should contain (as text): TwoLetterLanguageCodeEnum
    """

    embed_url: str
    """
    Used for photo embeds, instead of custom `html`.
    Should contain (as text): URL
    """

    _version = "3.2.0"

class Search(AttribAccessDict):
    """A search result, with accounts, hashtags and statuses.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Search/
    """

    accounts: EntityList[Account]
    """
    List of Accounts resulting from the query.
    """

    hashtags: EntityList[str]
    """
    THIS FIELD IS DEPRECATED. IT IS RECOMMENDED THAT YOU DO NOT USE IT.

    List of Tags resulting from the query.
      * 2.4.1: v1 search deprecated because it returns a list of strings. v2 search added which returns a list of tags.
      * 3.0.0: v1 removed
    """

    statuses: EntityList[Status]
    """
    List of Statuses resulting from the query.
    """

    _version = "3.0.0"

class SearchV2(AttribAccessDict):
    """A search result, with accounts, hashtags and statuses.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Search/
    """

    accounts: EntityList[Account]
    """
    List of Accounts resulting from the query.
    """

    hashtags: EntityList[Tag]
    """
    List of Tags resulting from the query.
    """

    statuses: EntityList[Status]
    """
    List of Statuses resulting from the query.
    """

    _version = "2.4.1"

class Instance(AttribAccessDict):
    """Information about an instance. V1 API version.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/V1_Instance/
    """

    uri: str
    """
    The instance's domain name. Moved to 'domain' for the v2 API, though Mastodon.py will mirror it here for backwards compatibility.
    Should contain (as text): DomainName
    """

    title: str
    """
    The instance's title.
    """

    short_description: str
    """
    An very brief text only instance description. Moved to 'description' for the v2 API.
    """

    description: str
    """
    THIS FIELD IS DEPRECATED. IT IS RECOMMENDED THAT YOU DO NOT USE IT.

    A brief instance description set by the admin. The V1 variant could contain html, but this is now deprecated. Likely to be empty on many instances.
    Should contain (as text): HTML
      * 4.0.0: deprecated - likely to be empty.
    """

    email: str
    """
    The admin contact email. Moved to InstanceContacts for the v2 API, though Mastodon.py will mirror it here for backwards compatibility.
    Should contain (as text): Email
    """

    version: str
    """
    The instance's Mastodon version. For a more robust parsed major/minor/patch version see TODO IMPLEMENT FUNCTION TO RETURN VERSIONS.
    """

    urls: InstanceURLs
    """
    Additional InstanceURLs, in the v1 api version likely to be just 'streaming_api' with the stream server websocket address.
    """

    stats: InstanceStatistics | None
    """
    InstanceStatistics containing three stats, user_count (number of local users), status_count (number of local statuses) and domain_count (number of known instance domains other than this one). This information is not present in the v2 API variant in this form - there is a 'usage' field instead. (optional)
    """

    thumbnail: str | None
    """
    Information about thumbnails to represent the instance. In the v1 API variant, simply an URL pointing to a banner image representing the instance. The v2 API provides a more complex structure with a list of thumbnails of different sizes in this field. (nullable)
    Should contain (as text): URL
    """

    languages: EntityList[str]
    """
    Array of ISO 639-1 (two-letter) language codes the instance has chosen to advertise.
    Should contain (as text): TwoLetterLanguageCodeEnum
    """

    registrations: bool
    """
    A boolean indication whether registrations on this instance are open (True) or not (False). The v2 API variant instead provides a dict with more information about possible registration requirements here.
    """

    approval_required: bool
    """
    True if account approval is required when registering, False if not. Moved to InstanceRegistrations object for the v2 API.
    """

    invites_enabled: bool
    """
    THIS FIELD IS DEPRECATED. IT IS RECOMMENDED THAT YOU DO NOT USE IT.

    Boolean indicating whether invites are enabled on this instance. Changed in 4.0.0 from being true when the instance setting to enable invites is true to be true when the default user role has invites enabled (i.e. everyone can invite people). The v2 API does not contain this field, and it is not clear whether it will stay around.
      * 4.0.0: changed specifics of when field is true, deprecated
    """

    configuration: InstanceConfiguration
    """
    Various instance configuration settings - especially various limits (character counts, media upload sizes, ...).
    """

    contact_account: Account
    """
    Account of the primary contact for the instance. Moved to InstanceContacts for the v2 API.
    """

    rules: EntityList[Rule]
    """
    List of Rules with `id` and `text` fields, one for each server rule set by the admin.
    """

    _version = "4.0.0"
    _access_map = {
        "uri": "domain",
        "short_description": "description",
        "email": "contact.email",
        "urls": "configuration.urls",
        "contact_account": "contact.account",
    }

class InstanceConfiguration(AttribAccessDict):
    """Configuration values for this instance, especially limits and enabled features.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/methods/instance/
    """

    accounts: InstanceAccountConfiguration
    """
    Account-related instance configuration fields.
    """

    statuses: InstanceStatusConfiguration
    """
    Status-related instance configuration fields.
    """

    media_attachments: InstanceMediaConfiguration
    """
    Media-related instance configuration fields.
    """

    polls: InstancePollConfiguration
    """
    Poll-related instance configuration fields.
    """

    _version = "3.4.2"

class InstanceURLs(AttribAccessDict):
    """A list of URLs related to an instance.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/V1_Instance/
    """

    streaming_api: str
    """
    The Websockets URL for connecting to the streaming API. Renamed to 'streaming' for the v2 API.
    Should contain (as text): URL
    """

    _version = "3.4.2"
    _access_map = {
        "streaming_api": "streaming",
    }

class InstanceV2(AttribAccessDict):
    """Information about an instance.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Instance/
    """

    domain: str
    """
    The instances domain name.
    Should contain (as text): DomainName
    """

    title: str
    """
    The instance's title.
    """

    version: str
    """
    The instance's Mastodon version. For a more robust parsed major/minor/patch version see TODO IMPLEMENT FUNCTION TO RETURN VERSIONS.
    """

    source_url: str
    """
    URL pointing to a copy of the source code that is used to run this instance. For Mastodon instances, the AGPL requires that this code be available.
    Should contain (as text): URL
    """

    description: str
    """
    A brief instance description set by the admin. Contains what in the v1 version was the short description.
    Should contain (as text): HTML
    """

    usage: InstanceUsage
    """
    Information about recent activity on this instance.
    """

    thumbnail: InstanceThumbnail | None
    """
    Information about thumbnails to represent the instance. (nullable)
    """

    languages: EntityList[str]
    """
    Array of ISO 639-1 (two-letter) language codes the instance has chosen to advertise.
    Should contain (as text): TwoLetterLanguageCodeEnum
    """

    configuration: InstanceConfiguration
    """
    Various instance configuration settings - especially various limits (character counts, media upload sizes, ...).
    """

    registrations: InstanceRegistrations
    """
    InstanceRegistrations object with information about how users can sign up on this instance.
    """

    contact: InstanceContact
    """
    Contact information for this instance.
    """

    rules: EntityList[Rule]
    """
    List of Rules with `id` and `text` fields, one for each server rule set by the admin.
    """

    _version = "4.0.0"

class InstanceConfigurationV2(AttribAccessDict):
    """Configuration values for this instance, especially limits and enabled features.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/methods/instance/
    """

    accounts: InstanceAccountConfiguration
    """
    Account-related instance configuration fields.
    """

    statuses: InstanceStatusConfiguration
    """
    Status-related instance configuration fields.
    """

    media_attachments: InstanceMediaConfiguration
    """
    Media-related instance configuration fields.
    """

    polls: InstancePollConfiguration
    """
    Poll-related instance configuration fields.
    """

    translation: InstanceTranslationConfiguration
    """
    Translation-related instance configuration fields. Only present for the v2 API variant of the instance API.
    """

    urls: InstanceURLsV2
    """
    Instance related URLs. Only present for the v2 API variant of the instance API.
    """

    _version = "4.0.0"

class InstanceURLsV2(AttribAccessDict):
    """A list of URLs related to an instance.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Instance/
    """

    streaming: str
    """
    The Websockets URL for connecting to the streaming API.
    Should contain (as text): URL
    """

    status: str | None
    """
    If present, a URL where the status and possibly current issues with the instance can be checked. (optional)
    Should contain (as text): URL
    """

    _version = "4.0.0"

class InstanceThumbnail(AttribAccessDict):
    """Extended information about an instances thumbnail.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/V1_Instance/
    """

    url: str
    """
    The URL for an image representing the instance.
    Should contain (as text): URL
    """

    blurhash: str | None
    """
    The blurhash for the image representing the instance. (optional)
    Should contain (as text): Blurhash
    """

    versions: InstanceThumbnailVersions | None
    """
    Different resolution versions of the image representing the instance. (optional)
    """

    _version = "4.0.0"

class InstanceThumbnailVersions(AttribAccessDict):
    """Different resolution versions of the image representing the instance.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Instance/
    """

    at1x: str | None
    """
    The URL for an image representing the instance, for devices with 1x resolution / 96 dpi. (optional)
    Should contain (as text): URL
    """

    at2x: str | None
    """
    The URL for the image representing the instance, for devices with 2x resolution / 192 dpi. (optional)
    Should contain (as text): URL
    """

    _version = "4.0.0"
    _rename_map = {
        "at1x": "@1x",
        "at2x": "@2x",
    }

class InstanceStatistics(AttribAccessDict):
    """Usage statistics for an instance.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Instance/
    """

    user_count: int
    """
    The total number of accounts that have been created on this instance.
    """

    status_count: int
    """
    The total number of local posts that have been made on this instance.
    """

    domain_count: int
    """
    The total number of other instances that this instance is aware of.
    """

    _version = "1.6.0"

class InstanceUsage(AttribAccessDict):
    """Usage / recent activity information for this instance.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Instance/
    """

    users: InstanceUsageUsers
    """
    Information about user counts on this instance.
    """

    _version = "3.0.0"

class InstanceUsageUsers(AttribAccessDict):
    """Recent active user information about this instance.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Instance/
    """

    active_month: int
    """
    This instances most recent monthly active user count.
    """

    _version = "3.0.0"

class Rule(AttribAccessDict):
    """A rule that instance staff has specified users must follow on this instance.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Rule/
    """

    id: IdType
    """
    An identifier for the rule.
    """

    text: str
    """
    The rule to be followed.
    """

    _version = "3.4.0"

class InstanceRegistrations(AttribAccessDict):
    """Registration information for this instance, like whether registrations are open and whether they require approval.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Instance/
    """

    approval_required: bool
    """
    Boolean indicating whether registrations on the instance require approval.
    """

    enabled: bool
    """
    Boolean indicating whether registrations are enabled on this instance.
    """

    message: str | None
    """
    A message to be shown instead of the sign-up form when registrations are closed. (nullable)
    Should contain (as text): HTML
    """

    url: str | None
    """
    Presumably, a registration related URL. It is unclear what this is for. (nullable)
    Should contain (as text): URL
    """

    _version = "4.0.0"

class InstanceContact(AttribAccessDict):
    """Contact information for this instances' staff.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Instance/
    """

    account: Account
    """
    Account that has been designated as the instances contact account.
    """

    email: str
    """
    E-mail address that can be used to contact the instance staff.
    Should contain (as text): Email
    """

    _version = "4.0.0"

class InstanceAccountConfiguration(AttribAccessDict):
    """Configuration values relating to accounts.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/methods/instance/
    """

    max_featured_tags: int
    """
    The maximum number of featured tags that can be displayed on a profile.
    """

    _version = "4.0.0"

class InstanceStatusConfiguration(AttribAccessDict):
    """Configuration values relating to statuses.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/methods/instance/
    """

    max_characters: int
    """
    Maximum number of characters in a status this instance allows local users to use.
    """

    max_media_attachments: int
    """
    Maximum number of media attachments per status this instance allows local users to use.
    """

    characters_reserved_per_url: int
    """
    Number of characters that this instance counts a URL as when counting charaters.
    """

    _version = "3.4.2"

class InstanceTranslationConfiguration(AttribAccessDict):
    """Configuration values relating to translation.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/methods/instance/
    """

    enabled: bool
    """
    Boolean indicating whether the translation API is enabled on this instance.
    """

    _version = "4.0.0"

class InstanceMediaConfiguration(AttribAccessDict):
    """Configuration values relating to media attachments.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/methods/instance/
    """

    supported_mime_types: EntityList[str]
    """
    Mime types the instance accepts for media attachment uploads.
    """

    image_size_limit: int
    """
    Maximum size (in bytes) the instance will accept for image uploads.
    """

    image_matrix_limit: int
    """
    Maximum total number of pixels (i.e. width * height) the instance will accept for image uploads.
    """

    video_size_limit: int
    """
    Maximum size (in bytes) the instance will accept for video uploads.
    """

    video_frame_rate_limit: int
    """
    Maximum frame rate the instance will accept for video uploads.
    """

    video_matrix_limit: int
    """
    Maximum total number of pixels (i.e. width * height) the instance will accept for video uploads.
    """

    _version = "3.4.2"

class InstancePollConfiguration(AttribAccessDict):
    """Configuration values relating to polls.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/methods/instance/
    """

    max_options: int
    """
    How many poll options this instance allows local users to use per poll.
    """

    max_characters_per_option: int
    """
    Maximum number of characters this instance allows local users to use per poll option.
    """

    min_expiration: int
    """
    The shortest allowed duration for a poll on this instance, in seconds.
    """

    max_expiration: int
    """
    The longest allowed duration for a poll on this instance, in seconds.
    """

    _version = "3.4.2"

class Nodeinfo(AttribAccessDict):
    """The instances standardized NodeInfo data.

    See also (Mastodon API documentation): https://github.com/jhass/nodeinfo
    """

    version: str
    """
    Version of the nodeinfo schema spec that was used for this response.
    """

    software: NodeinfoSoftware
    """
    Information about the server software being used on this instance.
    """

    protocols: EntityList[str]
    """
    A list of strings specifying the federation protocols this instance supports. Typically, just "activitypub".
    """

    services: NodeinfoServices
    """
    Services that this instance can retrieve messages from or send messages to.
    """

    usage: NodeinfoUsage
    """
    Information about recent activity on this instance.
    """

    openRegistrations: bool
    """
    Bool indicating whether the instance is open for registrations.
    """

    metadata: NodeinfoMetadata
    """
    Additional node metadata. On Mastodon, typically an empty object with no fields.
    """

    _version = "3.0.0"

class NodeinfoSoftware(AttribAccessDict):
    """NodeInfo software-related information.

    See also (Mastodon API documentation): https://github.com/jhass/nodeinfo
    """

    name: str
    """
    Name of the software used by this instance.
    """

    version: str
    """
    String indicating the version of the software used by this instance.
    """

    _version = "3.0.0"

class NodeinfoServices(AttribAccessDict):
    """Nodeinfo services-related information.

    See also (Mastodon API documentation): https://github.com/jhass/nodeinfo
    """

    outbound: EntityList
    """
    List of services that this instance can send messages to. On Mastodon, typically an empty list.
    """

    inbound: EntityList
    """
    List of services that this instance can retrieve messages from. On Mastodon, typically an empty list.
    """

    _version = "3.0.0"

class NodeinfoUsage(AttribAccessDict):
    """Nodeinfo usage-related information.

    See also (Mastodon API documentation): https://github.com/jhass/nodeinfo
    """

    users: NodeinfoUsageUsers
    """
    Information about user counts on this instance.
    """

    localPosts: int
    """
    The total number of local posts that have been made on this instance.
    """

    _version = "3.0.0"

class NodeinfoUsageUsers(AttribAccessDict):
    """Nodeinfo user count statistics.

    See also (Mastodon API documentation): https://github.com/jhass/nodeinfo
    """

    total: int
    """
    The total number of accounts that have been created on this instance.
    """

    activeMonth: int
    """
    Number of users that have been active, by some definition (Mastodon: Have logged in at least once) in the last month.
    """

    activeHalfyear: int
    """
    Number of users that have been active, by some definition (Mastodon: Have logged in at least once) in the last half year.
    """

    _version = "3.0.0"

class NodeinfoMetadata(AttribAccessDict):
    """Nodeinfo extra metadata.

    See also (Mastodon API documentation): https://github.com/jhass/nodeinfo
    """

    _version = "0.0.0"

class Activity(AttribAccessDict):
    """Information about recent activity on an instance.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/methods/instance/#activity
    """

    week: datetime
    """
    Date of the first day of the week the stats were collected for.
    """

    logins: int
    """
    Number of users that logged in that week.
    """

    registrations: int
    """
    Number of new users that week.
    """

    statuses: int
    """
    Number of statuses posted that week.
    """

    _version = "2.1.2"

class Report(AttribAccessDict):
    """Information about a report that has been filed against a user. Currently largely pointless, as updated reports cannot be fetched.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Report/
    """

    id: IdType
    """
    Id of the report.
    """

    action_taken: bool
    """
    True if a moderator or admin has processed the report, False otherwise.
    """

    comment: str
    """
    Text comment submitted with the report.
    """

    created_at: datetime
    """
    Time at which this report was created, as a datetime object.
    """

    target_account: Account
    """
    Account that has been reported with this report.
    """

    status_ids: EntityList[IdType]
    """
    List of status IDs attached to the report.
    """

    action_taken_at: datetime | None
    """
    When an action was taken, if this report is currently resolved. (nullable)
    """

    category: str
    """
    The category under which the report is classified.
    Should contain (as text): ReportReasonEnum
    """

    forwarded: bool
    """
    Whether a report was forwarded to a remote instance.
    """

    rules_ids: EntityList[IdType]
    """
    IDs of the rules selected for this report.
    """

    _version = "4.0.0"

class AdminReport(AttribAccessDict):
    """Information about a report that has been filed against a user.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Admin_Report/
    """

    id: IdType
    """
    Id of the report.
    """

    action_taken: bool
    """
    True if a moderator or admin has processed the report, False otherwise.
    """

    comment: str
    """
    Text comment submitted with the report.
    """

    created_at: datetime
    """
    Time at which this report was created, as a datetime object.
    """

    updated_at: datetime
    """
    Last time this report has been updated, as a datetime object.
    """

    account: Account
    """
    Account of the user that filed this report.
    """

    target_account: Account
    """
    Account that has been reported with this report.
    """

    assigned_account: AdminAccount | None
    """
    If the report as been assigned to an account, that Account (None if not). (nullable)
    """

    action_taken_by_account: AdminAccount | None
    """
    Account that processed this report. (nullable)
    """

    statuses: EntityList[Status]
    """
    List of Statuses attached to the report.
    """

    action_taken_at: datetime | None
    """
    When an action was taken, if this report is currently resolved. (nullable)
    """

    category: str
    """
    The category under which the report is classified.
    Should contain (as text): ReportReasonEnum
    """

    forwarded: bool
    """
    Whether a report was forwarded to a remote instance.
    """

    rules: EntityList[Rule]
    """
    Rules attached to the report, for context.
    """

    _version = "4.0.0"

class WebPushSubscription(AttribAccessDict):
    """Information about the logged-in users web push subscription for the authenticated application.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/WebPushSubscription/
    """

    id: IdType
    """
    Id of the push subscription.
    """

    endpoint: str
    """
    Endpoint URL for the subscription.
    Should contain (as text): URL
    """

    server_key: str
    """
    Server pubkey used for signature verification.
    """

    alerts: WebPushSubscriptionAlerts
    """
    Subscribed events - object that may contain various keys, with value True if webpushes have been requested for those events.
      * 2.8.0: added poll`
      * 3.1.0: added follow_request`
      * 3.3.0: added status
      * 3.5.0: added update and admin.sign_up
      * 4.0.0: added admin.report
    """

    policy: str
    """
    Which sources should generate webpushes.
    """

    _version = "4.0.0"

class WebPushSubscriptionAlerts(AttribAccessDict):
    """Information about alerts as part of a push subscription.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/WebPushSubscription/
    """

    follow: bool
    """
    True if push subscriptions for follow events have been requested, false or not present otherwise.
    """

    favourite: bool
    """
    True if push subscriptions for favourite events have been requested, false or not present otherwise.
    """

    reblog: bool
    """
    True if push subscriptions for reblog events have been requested, false or not present otherwise.
    """

    mention: bool
    """
    True if push subscriptions for mention events have been requested, false or not present otherwise.
    """

    poll: bool
    """
    True if push subscriptions for poll events have been requested, false or not present otherwise.
    """

    follow_request: bool
    """
    True if push subscriptions for follow request events have been requested, false or not present otherwise.
    """

    status: bool
    """
    True if push subscriptions for status creation (watched users only) events have been requested, false or not present otherwise.
    """

    update: bool
    """
    True if push subscriptions for status update (edit) events have been requested, false or not present otherwise.
    """

    admin_sign_up: bool
    """
    True if push subscriptions for sign up events have been requested, false or not present otherwise. Admins only.
    """

    admin_report: bool
    """
    True if push subscriptions for report creation events have been requested, false or not present otherwise. Admins only.
    """

    _version = "4.0.0"

class PushNotification(AttribAccessDict):
    """A single Mastodon push notification received via WebPush, after decryption.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/WebPushSubscription/
    """

    access_token: str
    """
    Access token that can be used to access the API as the notified user.
    """

    body: str
    """
    Text body of the notification.
    """

    icon: str
    """
    URL to an icon for the notification.
    Should contain (as text): URL
    """

    notification_id: IdType
    """
    ID that can be passed to notification() to get the full notification object,.
    """

    notification_type: str
    """
    String indicating the type of notification.
    """

    preferred_locale: str
    """
    The user's preferred locale.
    Should contain (as text): TwoLetterLanguageCodeEnum
    """

    title: str
    """
    Title for the notification.
    """

    _version = "2.4.0"

class Preferences(AttribAccessDict):
    """The logged in users preferences.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Preferences/
    """

    posting_default_visibility: str
    """
    Default visibility for new posts. Also found in CredentialAccountSource as `privacy`.
    """

    posting_default_sensitive: bool
    """
    Default sensitivity flag for new posts. Also found in CredentialAccountSource as `sensitive`.
    """

    posting_default_language: str | None
    """
    Default language for new posts. Also found in CredentialAccountSource as `language`. (nullable)
    Should contain (as text): TwoLetterLanguageCodeEnum
    """

    reading_expand_media: str
    """
    String indicating whether media attachments should be automatically displayed or blurred/hidden.
    """

    reading_expand_spoilers: bool
    """
    Boolean indicating whether CWs should be expanded by default.
    """

    reading_autoplay_gifs: bool
    """
    Boolean indicating whether gifs should be autoplayed (True) or not (False).
    """

    _version = "2.8.0"
    _rename_map = {
        "posting_default_visibility": "posting:default:visibility",
        "posting_default_sensitive": "posting:default:sensitive",
        "posting_default_language": "posting:default:language",
        "reading_expand_media": "reading:expand:media",
        "reading_expand_spoilers": "reading:expand:spoilers",
        "reading_autoplay_gifs": "reading:autoplay:gifs",
    }

class FeaturedTag(AttribAccessDict):
    """A tag featured on a users profile.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/FeaturedTag/
    """

    id: IdType
    """
    The featured tags id.
    """

    name: str
    """
    The featured tags name (without leading #).
    """

    statuses_count: str
    """
    Number of publicly visible statuses posted with this hashtag that this instance knows about.
    """

    last_status_at: datetime
    """
    The last time a public status containing this hashtag was added to this instance's database (can be None if there are none).
    """

    url: str
    """
    A link to all statuses by a user that contain this hashtag.
    Should contain (as text): URL
    """

    _version = "3.3.0"

class Marker(AttribAccessDict):
    """A read marker indicating where the logged in user has left off reading a given timeline.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Marker/
    """

    last_read_id: IdType
    """
    ID of the last read object in the timeline.
    """

    version: int
    """
    A counter that is incremented whenever the marker is set to a new status.
    """

    updated_at: datetime
    """
    The time the marker was last set, as a datetime object.
    """

    _version = "3.0.0"

class Announcement(AttribAccessDict):
    """An announcement sent by the instances staff.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Announcement/
    """

    id: IdType
    """
    The annoucements id.
    """

    content: str
    """
    The contents of the annoucement, as an html string.
    Should contain (as text): HTML
    """

    starts_at: datetime | None
    """
    The annoucements start time, as a datetime object. Can be None. (nullable)
    """

    ends_at: datetime | None
    """
    The annoucements end time, as a datetime object. Can be None. (nullable)
    """

    all_day: bool
    """
    Boolean indicating whether the annoucement represents an "all day" event.
    """

    published_at: datetime
    """
    The annoucements publish time, as a datetime object.
    """

    updated_at: datetime
    """
    The annoucements last updated time, as a datetime object.
    """

    read: bool
    """
    A boolean indicating whether the logged in user has dismissed the annoucement.
    """

    mentions: EntityList[StatusMention]
    """
    Users mentioned in the annoucement.
    """

    tags: EntityList
    """
    Hashtags mentioned in the announcement.
    """

    emojis: EntityList
    """
    Custom emoji used in the annoucement.
    """

    reactions: EntityList[Reaction]
    """
    Reactions to the annoucement.
    """

    statuses: EntityList
    """
    Statuses linked in the announcement text.
    """

    _version = "3.1.0"

class Reaction(AttribAccessDict):
    """A reaction to an announcement.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Reaction/
    """

    name: str
    """
    Name of the custom emoji or unicode emoji of the reaction.
    """

    count: int
    """
    Reaction counter (i.e. number of users who have added this reaction).
    """

    me: bool
    """
    True if the logged-in user has reacted with this emoji, false otherwise.
    """

    url: str
    """
    URL for the custom emoji image.
    Should contain (as text): URL
    """

    static_url: str
    """
    URL for a never-animated version of the custom emoji image.
    Should contain (as text): URL
    """

    _version = "3.1.0"

class StreamReaction(AttribAccessDict):
    """A reaction to an announcement.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/methods/streaming/
    """

    name: str
    """
    Name of the custom emoji or unicode emoji of the reaction.
    """

    count: int
    """
    Reaction counter (i.e. number of users who have added this reaction).
    """

    announcement_id: IdType
    """
    If of the announcement this reaction was for.
    """

    _version = "3.1.0"

class FamiliarFollowers(AttribAccessDict):
    """A follower of a given account that is also followed by the logged-in user.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/FamiliarFollowers/
    """

    id: IdType
    """
    ID of the account for which the familiar followers are being returned.
    """

    accounts: EntityList[Account]
    """
    List of Accounts of the familiar followers.
    """

    _version = "3.5.0"

class AdminAccount(AttribAccessDict):
    """Admin variant of the Account entity, with some additional information.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Admin_Account/
    """

    id: IdType
    """
    The users id,.
    """

    username: str
    """
    The users username, no leading @.
    """

    domain: str | None
    """
    The users domain. (nullable)
    """

    created_at: datetime
    """
    The time of account creation.
    """

    email: str
    """
    For local users, the user's email.
    Should contain (as text): Email
    """

    ip: str | None
    """
    For local users, the user's last known IP address. (nullable)
      * 3.5.0: return type changed from String to [AdminIp]({{< relref "entities/Admin_Ip" >}}) due to a bug
      * 4.0.0: bug fixed, return type is now a String again
    """

    role: Role
    """
    The users role., returns a String (enumerable, oneOf `user` `moderator` `admin`)
      * 4.0.0: now uses Role entity
    """

    confirmed: bool
    """
    For local users, False if the user has not confirmed their email, True otherwise.
    """

    suspended: bool
    """
    Boolean indicating whether the user has been suspended.
    """

    silenced: bool
    """
    Boolean indicating whether the user has been silenced.
    """

    disabled: bool
    """
    For local users, boolean indicating whether the user has had their login disabled.
    """

    approved: bool
    """
    For local users, False if the user is pending, True otherwise.
    """

    locale: str
    """
    For local users, the locale the user has set,.
    Should contain (as text): TwoLetterLanguageCodeEnum
    """

    invite_request: str | None
    """
    If the user requested an invite, the invite request comment of that user. (nullable)
    """

    account: Account
    """
    The user's Account.
    """

    sensitized: bool
    """
    Undocumented. If you know what this means, please let me know.
    """

    ips: EntityList[AdminIp]
    """
    All known IP addresses associated with this account.
    """

    created_by_application_id: IdType | None
    """
    Present if the user was created by an application and set to the application id. (optional)
    """

    invited_by_account_id : IdType | None
    """
    Present if the user was created via invite and set to the inviting users id. (optional)
    """

    _version = "4.0.0"

class AdminIp(AttribAccessDict):
    """An IP address used by some user or other instance, visible as part of some admin APIs.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Admin_Ip/
    """

    ip: str
    """
    The IP address.
    """

    used_at: str
    """
    The timestamp of when the IP address was last used for this account.
    """

    _version = "3.5.0"

class AdminMeasure(AttribAccessDict):
    """A measurement, such as the number of active users, as returned by the admin reporting API.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Admin_Measure/
    """

    key: str
    """
    Name of the measure returned.
    Should contain (as text): AdminMeasureTypeEnum
    """

    unit: str | None
    """
    Unit for the measure, if available. (nullable)
    """

    total: str
    """
    Value of the measure returned.
    """

    human_value: str
    """
    Human readable variant of the measure returned.
    """

    previous_total: str | None
    """
    Previous measurement period value of the measure returned, if available. (nullable)
    """

    data: EntityList[AdminMeasureData]
    """
    A list of AdminMeasureData with the measure broken down by date.
    """

    _version = "3.5.0"

class AdminMeasureData(AttribAccessDict):
    """A single row of data for an admin reporting api measurement.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Admin_Measure/
    """

    date: datetime
    """
    Date for this row.
    """

    value: int
    """
    Value of the measure for this row.
    """

    _version = "3.5.0"

class AdminDimension(AttribAccessDict):
    """A qualitative measurement about the server, as returned by the admin reporting api.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Admin_Dimension/
    """

    key: str
    """
    Name of the dimension returned.
    """

    data: EntityList[AdminDimensionData]
    """
    A list of data AdminDimensionData objects.
    """

    _version = "3.5.0"

class AdminDimensionData(AttribAccessDict):
    """A single row of data for qualitative measurements about the server, as returned by the admin reporting api.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Admin_Dimension/
    """

    key: str
    """
    category for this row.
    """

    human_key: str
    """
    Human readable name for the category for this row, when available.
    """

    value: int
    """
    Numeric value for the category.
    """

    _version = "3.5.0"

class AdminRetention(AttribAccessDict):
    """User retention data for a given cohort, as returned by the admin reporting api.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Admin_Cohort/
    """

    period: datetime
    """
    Starting time of the period that the data is being returned for.
    """

    frequency: str
    """
    Time resolution (day or month) for the returned data.
    """

    data: EntityList[AdminCohort]
    """
    List of AdminCohort objects.
    """

    _version = "3.5.0"

class AdminCohort(AttribAccessDict):
    """A single data point regarding user retention for a given cohort, as returned by the admin reporting api.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Admin_Cohort/
    """

    date: datetime
    """
    Date for this entry.
    """

    rate: float
    """
    Fraction of users retained.
    """

    value: int
    """
    Absolute number of users retained.
    """

    _version = "3.5.0"

class AdminDomainBlock(AttribAccessDict):
    """A domain block, as returned by the admin API.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Admin_DomainBlock/
    """

    id: IdType
    """
    The ID of the DomainBlock in the database.
    """

    domain: str
    """
    The domain that is not allowed to federate.
    """

    created_at: datetime
    """
    When the domain was blocked from federating.
    """

    severity: str
    """
    The policy to be applied by this domain block.
    Should contain (as text): AdminDomainLimitEnum
    """

    reject_media: bool
    """
    Whether to reject media attachments from this domain.
    """

    reject_reports: bool
    """
    Whether to reject reports from this domain.
    """

    private_comment: str | None
    """
    A private comment (visible only to other moderators) for the domain block. (nullable)
    """

    public_comment: str | None
    """
    A public comment (visible to either all users, or the whole world) for the domain block. (nullable)
    """

    obfuscate: bool
    """
    Whether to obfuscate public displays of this domain block.
    """

    _version = "4.0.0"

class AdminCanonicalEmailBlock(AttribAccessDict):
    """An e-mail block that has been set up to prevent certain e-mails to be used when signing up, via hash matching.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Admin_CanonicalEmailBlock
    """

    id: IdType
    """
    The ID of the email block in the database.
    """

    canonical_email_hash: str
    """
    The SHA256 hash of the canonical email address.
    """

    _version = "4.0.0"

class AdminDomainAllow(AttribAccessDict):
    """The opposite of a domain block, specifically allowing a domain to federate when the instance is in allowlist mode.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Admin_DomainAllow
    """

    id: IdType
    """
    The ID of the DomainAllow in the database.
    """

    domain: str
    """
    The domain that is allowed to federate.
    """

    created_at: datetime
    """
    When the domain was allowed to federate.
    """

    _version = "4.0.0"

class AdminEmailDomainBlock(AttribAccessDict):
    """A block that has been set up to prevent e-mails from certain domains to be used when signing up.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Admin_EmailDomainBlock
    """

    id: IdType
    """
    The ID of the EmailDomainBlock in the database.
    """

    domain: str
    """
    The email domain that is not allowed to be used for signups.
    """

    created_at: datetime
    """
    When the email domain was disallowed from signups.
    """

    history: EntityList[AdminEmailDomainBlockHistory]
    """
    Usage statistics for given days (typically the past week).
    """

    _version = "4.0.0"

class AdminEmailDomainBlockHistory(AttribAccessDict):
    """Historic data about attempted signups using e-mails from a given domain.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Admin_EmailDomainBlock
    """

    day: datetime
    """
    The time (in day increments) for which this row of historical data is valid.
    """

    accounts: int
    """
    The number of different account creation attempts that have been made.
    """

    uses: int
    """
    The number of different ips used in account creation attempts.
    """

    _version = "4.0.0"

class AdminIpBlock(AttribAccessDict):
    """An admin IP block, to prevent certain IP addresses or address ranges from accessing the instance.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Admin_IpBlock
    """

    id: IdType
    """
    The ID of the DomainBlock in the database.
    """

    ip: str
    """
    The IP address range that is not allowed to federate.
    """

    severity: str
    """
    The associated policy with this IP block.
    """

    comment: str
    """
    The recorded reason for this IP block.
    """

    created_at: datetime
    """
    When the IP block was created.
    """

    expires_at: datetime | None
    """
    When the IP block will expire. (nullable)
    """

    _version = "4.0.0"

class DomainBlock(AttribAccessDict):
    """A domain block that has been implemented by instance staff, limiting the way posts from the blocked instance are handled.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/DomainBlock
    """

    domain: str
    """
    The domain which is blocked. This may be obfuscated or partially censored.
    """

    digest: str
    """
    The SHA256 hash digest of the domain string.
    """

    severity: str
    """
    The level to which the domain is blocked.
    Should contain (as text): DomainLimitEnum
    """

    comment: str
    """
    An optional reason for the domain block.
    """

    _version = "4.0.0"

class ExtendedDescription(AttribAccessDict):
    """An extended instance description that can contain HTML.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/ExtendedDescription
    """

    updated_at: datetime
    """
    A timestamp of when the extended description was last updated.
    """

    content: str
    """
    The rendered HTML content of the extended description.
    Should contain (as text): HTML
    """

    _version = "4.0.0"

class FilterKeyword(AttribAccessDict):
    """A keyword that is being matched as part of a filter.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/FilterKeyword
    """

    id: IdType
    """
    The ID of the FilterKeyword in the database.
    """

    keyword: str
    """
    The phrase to be matched against.
    """

    whole_word: bool
    """
    Should the filter consider word boundaries? See implementation guidelines for filters().
    """

    _version = "4.0.0"

class FilterStatus(AttribAccessDict):
    """A single status that is being matched as part of a filter.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/FilterStatus
    """

    id: IdType
    """
    The ID of the FilterStatus in the database.
    """

    status_id: MaybeSnowflakeIdType
    """
    The ID of the Status that will be filtered.
    """

    _version = "4.0.0"

class IdentityProof(AttribAccessDict):
    """A cryptographic proof-of-identity.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/IdentityProof
    """

    provider: str
    """
    The name of the identity provider.
    """

    provider_username: str
    """
    The account owner's username on the identity provider's service.
    """

    updated_at: datetime
    """
    When the identity proof was last updated.
    """

    proof_url: str
    """
    A link to a statement of identity proof, hosted by the identity provider.
    """

    profile_url: str
    """
    The account owner's profile URL on the identity provider.
    """

    _version = "2.8.0"

class StatusSource(AttribAccessDict):
    """The source data of a status, useful when editing a status.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/StatusSource
    """

    id: IdType
    """
    ID of the status in the database.
    """

    text: str
    """
    The plain text used to compose the status.
    """

    spoiler_text: str
    """
    The plain text used to compose the status's subject or content warning.
    """

    _version = "3.5.0"

class Suggestion(AttribAccessDict):
    """A follow suggestion.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Suggestion
    """

    source: str
    """
    The reason this account is being suggested.
    """

    account: Account
    """
    The account being recommended to follow.
    """

    _version = "3.4.0"

class Translation(AttribAccessDict):
    """A translation of a status.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/entities/Translation
    """

    content: str
    """
    The translated text of the status.
    """

    detected_source_language: str
    """
    The language of the source text, as auto-detected by the machine translation provider.
    """

    provider: str
    """
    The service that provided the machine translation.
    """

    _version = "4.0.0"

class AccountCreationError(AttribAccessDict):
    """An error response returned when creating an account fails.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/methods/accounts/#create
    """

    error: str
    """
    The error as a localized string.
    """

    details: AccountCreationErrorDetails
    """
    A dictionary giving more details about what fields caused errors and in which ways.
    """

    _version = "3.4.0"

class AccountCreationErrorDetails(AttribAccessDict):
    """An object containing detailed errors for different fields in the account creation attempt.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/methods/accounts/#create
    """

    username: AccountCreationErrorDetailsField | None
    """
    An object giving more details about an error caused by the username. (optional)
    """

    password: AccountCreationErrorDetailsField | None
    """
    An object giving more details about an error caused by the password. (optional)
    """

    email: AccountCreationErrorDetailsField | None
    """
    An object giving more details about an error caused by the e-mail. (optional)
    """

    agreement: AccountCreationErrorDetailsField | None
    """
    An object giving more details about an error caused by the usage policy agreement. (optional)
    """

    locale: AccountCreationErrorDetailsField | None
    """
    An object giving more details about an error caused by the locale. (optional)
    """

    reason: AccountCreationErrorDetailsField | None
    """
    An object giving more details about an error caused by the registration reason. (optional)
    """

    _version = "3.4.0"

class AccountCreationErrorDetailsField(AttribAccessDict):
    """An object giving details about what specifically is wrong with a given field in an account registration attempt.

    See also (Mastodon API documentation): https://docs.joinmastodon.org/methods/accounts/#create
    """

    error: str
    """
    A machine readable string giving an error category.
    """

    description: str
    """
    A description of the issue as a localized string.
    """

    _version = "3.4.0"
