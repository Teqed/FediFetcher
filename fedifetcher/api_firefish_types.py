"""Types for the Firefish API."""
from typing import Any, Optional


class UserDetailedNotMe:
    """A class representing an ActivityPub object."""

    def __init__(
        self,
        id: str,
        name: str | None,
        username: str,
        host: str | None,
        avatarUrl: str,
        avatarBlurhash: str | None,
        avatarColor: str | None,
        isAdmin: bool,
        isModerator: bool,
        isBot: bool,
        isCat: bool,
        speakAsCat: bool,
        emojis: list[dict],
        onlineStatus: str | None,
        url: str | None,
        uri: str | None,
        movedToUri: str | None,
        alsoKnownAs: list[str] | None,
        createdAt: str,
        updatedAt: str | None,
        lastFetchedAt: str | None,
        bannerUrl: str | None,
        bannerBlurhash: str | None,
        bannerColor: str | None,
        isLocked: bool,
        isSilenced: bool,
        isSuspended: bool,
        description: str | None,
        location: str | None,
        birthday: str | None,
        lang: str | None,
        fields: list[dict],
        followersCount: int,
        followingCount: int,
        notesCount: int,
        pinnedNoteIds: list[str],
        pinnedNotes: list[dict],
        pinnedPageId: str | None,
        pinnedPage: dict,
        publicReactions: bool,
        twoFactorEnabled: bool,
        usePasswordLessLogin: bool,
        securityKeys: bool,
        isFollowing: bool | None,
        isFollowed: bool | None,
        hasPendingFollowRequestFromYou: bool | None,
        hasPendingFollowRequestToYou: bool | None,
        isBlocking: bool | None,
        isBlocked: bool | None,
        isMuted: bool | None,
        isRenoteMuted: bool | None,
        reactionEmojis: list[dict],
    ) -> None:
        """Initialize a UserDetailedNotMe object."""
        self.id = id
        self.name = name
        self.username = username
        self.host = host
        self.avatarUrl = avatarUrl
        self.avatarBlurhash = avatarBlurhash
        self.avatarColor = avatarColor
        self.isAdmin = isAdmin
        self.isModerator = isModerator
        self.isBot = isBot
        self.isCat = isCat
        self.speakAsCat = speakAsCat
        self.emojis = emojis
        self.onlineStatus = onlineStatus
        self.url = url
        self.uri = uri
        self.movedToUri = movedToUri
        self.alsoKnownAs = alsoKnownAs
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.lastFetchedAt = lastFetchedAt
        self.bannerUrl = bannerUrl
        self.bannerBlurhash = bannerBlurhash
        self.bannerColor = bannerColor
        self.isLocked = isLocked
        self.isSilenced = isSilenced
        self.isSuspended = isSuspended
        self.description = description
        self.location = location
        self.birthday = birthday
        self.lang = lang
        self.fields = fields
        self.followersCount = followersCount
        self.followingCount = followingCount
        self.notesCount = notesCount
        self.pinnedNoteIds = pinnedNoteIds
        self.pinnedNotes = pinnedNotes
        self.pinnedPageId = pinnedPageId
        self.pinnedPage = pinnedPage
        self.publicReactions = publicReactions
        self.twoFactorEnabled = twoFactorEnabled
        self.usePasswordLessLogin = usePasswordLessLogin
        self.securityKeys = securityKeys
        self.isFollowing = isFollowing
        self.isFollowed = isFollowed
        self.hasPendingFollowRequestFromYou = hasPendingFollowRequestFromYou
        self.hasPendingFollowRequestToYou = hasPendingFollowRequestToYou
        self.isBlocking = isBlocking
        self.isBlocked = isBlocked
        self.isMuted = isMuted
        self.isRenoteMuted = isRenoteMuted
        self.reactionEmojis = reactionEmojis

class UserLite:
    def __init__(
        self,
        id: str,
        name: str | None,
        username: str,
        host: str | None,
        avatarUrl: str | None,
        avatarBlurhash: str | int | None,
        avatarColor: str | int | None,
        isAdmin: bool = False,
        isModerator: bool = False,
        isBot: bool = False,
        isCat: bool = False,
        speakAsCat: bool = False,
        emojis: list[dict[str, str]] | None = None,
        onlineStatus: str | None = None,
    ) -> None:
        self.id = id
        self.name = name
        self.username = username
        self.host = host
        self.avatarUrl = avatarUrl
        self.avatarBlurhash = avatarBlurhash
        self.avatarColor = avatarColor
        self.isAdmin = isAdmin
        self.isModerator = isModerator
        self.isBot = isBot
        self.isCat = isCat
        self.speakAsCat = speakAsCat
        self.emojis = emojis
        self.onlineStatus = onlineStatus

class DriveFile:
    def __init__(
        self,
        id: str,
        createdAt: str,
        name: str,
        type: str,
        md5: str,
        size: int,
        isSensitive: bool,
        blurhash: str | None,
        properties: dict[str, int | str],
        url: str | None,
        thumbnailUrl: str | None,
        comment: str | None,
        folderId: str | None,
        folder: dict[str, str | int] | None,
        userId: str | None,
        user: UserLite | None,
    ) -> None:
        self.id = id
        self.createdAt = createdAt
        self.name = name
        self.type = type
        self.md5 = md5
        self.size = size
        self.isSensitive = isSensitive
        self.blurhash = blurhash
        self.properties = properties
        self.url = url
        self.thumbnailUrl = thumbnailUrl
        self.comment = comment
        self.folderId = folderId
        self.folder = folder
        self.userId = userId
        self.user = user

class Note:
    def __init__(
        self,
        id: str,
        createdAt: str,
        text: str | None,
        cw: str | None,
        userId: str,
        user: "UserLite",
        replyId: str | None,
        renoteId: str | None,
        renoteCount: int,
        repliesCount: int,
        uri: str,
        url: str | None = None,
        reply: Optional["Note"] | None = None,
        renote: Optional["Note"] | None = None,
        visibility: str | None = None,
        mentions: list[str] | None = None,
        visibleUserIds: list[str] | None = None,
        fileIds: list[str] | None = None,
        files: list["DriveFile"] | None = None,
        tags: list[str] | None = None,
        poll: (dict[str, str | int | list[str]]) | None = None,
        channelId: str | None = None,
        channel: dict[str, str | int | list[str | int | None]] | None = None,
        localOnly: bool | None = None,
        emojis: dict[str, str] | None = None,
        reactions: dict[str, int] | None = None,
        myReaction: dict[str, Any] | None = None,
        reactionEmojis: list[dict] | None = None,
    ) -> None:
        self.id = id
        self.createdAt = createdAt
        self.text = text
        self.cw = cw
        self.userId = userId
        self.user = user
        self.replyId = replyId
        self.renoteId = renoteId
        self.reply = reply if reply else None
        self.renote = renote if renote else None
        self.visibility = visibility
        self.mentions = mentions
        self.visibleUserIds = visibleUserIds if visibleUserIds else []
        self.fileIds = fileIds
        self.files = files
        self.tags = tags
        self.poll = poll if poll else None
        self.channelId = channelId if channelId else None
        self.channel = channel if channel else None
        self.localOnly = localOnly if localOnly else None
        self.emojis = emojis
        self.reactions = reactions
        self.renoteCount = renoteCount
        self.repliesCount = repliesCount
        self.uri = uri
        self.url = url if url else uri
        self.myReaction = myReaction if myReaction else None
        self.in_reply_to_id = replyId
        self.in_reply_to_account_id = None
        self.reblog = reply
        self.content = text
        self.reblogs_count = renoteCount
        self.favourites_count = 0
        if reactions and self.favourites_count:
            for reaction in reactions:
                self.favourites_count += reactions.get(reaction)
        self.reblogged = None
        self.favourited = None
        self.sensitive = None
        self.spoiler_text = cw
        self.media_attachments = None
        self.bookmarked = None
        self.application = None
        self.language = None
        self.muted = None
        self.pinned = None
        self.replies_count = repliesCount
        self.card = None
        self.reactionEmojis = reactionEmojis

    def get(self, attr, default=None) -> Any:
        return getattr(self, attr, default)

class ErrorResponse:
    """A class representing an error response from the API."""

    def __init__(self, raw_data: dict) -> None:
        """Initialize an ErrorResponse object."""
        self.message = raw_data["error"]["message"]
        self.code = raw_data["error"]["code"]
        self.id = raw_data["error"]["id"]
