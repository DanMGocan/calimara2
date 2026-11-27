from .base import Base
from .users import User
from .writing import DiacriticsUsageEvent
from .content import PostDraft, Post, PostAudio, AudioPlaylist, AudioPlaylistItem, PostReport, Comment, CommentReaction, Like, SuperLike
from .portability import UserDataImport, ImportedPostSnapshot
from .premium import StripeEvent
from .jobs import AIJob
from .profile import BestFriend, FeaturedPost, UserAward
from .series import Series, SeriesPost
from .clubs import Club, ClubMember, ClubJoinRequest, ClubBoardMessage, ClubAchievement
from .theatre import TheatrePlay, TheatreMember, TheatreCharacter, TheatreJoinRequest, TheatreScene, TheatreEntry
from .stafeta import StafetaParticipant, StafetaWork, StafetaAssignment, StafetaSegment
from .economy import GologaniTransaction, GologaniRewardSetting, ShopItem, UserInventoryItem, UserEquippedItem
from .forum import ForumSection, ForumThread, ForumReply, ForumThreadRead, ForumThreadFollow, ForumReplyLike
from .messaging import Conversation, Message
from .social import Friendship, UserFollow
from .moderation import ModerationLog, ModerationWord
from .notifications import Notification
from .statistics import AudioListenEvent, PageView, DailyStat
from .admin import AdminAuditLog, AdminDailyMetric, AdminPerformanceSnapshot, PlatformAccessSetting, PlatformAllowedEmail, PlatformInvitation, SiteFeedback
from .email import EmailCampaign, EmailOutbox
from .auth import AuthEmailCode

__all__ = [
    "Base",
    "User",
    "DiacriticsUsageEvent",
    "PostDraft",
    "Post",
    "PostAudio",
    "AudioPlaylist",
    "AudioPlaylistItem",
    "PostReport",
    "Comment",
    "CommentReaction",
    "Like",
    "SuperLike",
    "UserDataImport",
    "ImportedPostSnapshot",
    "StripeEvent",
    "AIJob",
    "BestFriend",
    "FeaturedPost",
    "UserAward",
    "Series",
    "SeriesPost",
    "Club",
    "ClubMember",
    "ClubJoinRequest",
    "ClubBoardMessage",
    "ClubAchievement",
    "TheatrePlay",
    "TheatreMember",
    "TheatreCharacter",
    "TheatreJoinRequest",
    "TheatreScene",
    "TheatreEntry",
    "StafetaParticipant",
    "StafetaWork",
    "StafetaAssignment",
    "StafetaSegment",
    "GologaniTransaction",
    "GologaniRewardSetting",
    "ShopItem",
    "UserInventoryItem",
    "UserEquippedItem",
    "ForumThread",
    "ForumReply",
    "ForumSection",
    "ForumThreadRead",
    "ForumThreadFollow",
    "ForumReplyLike",
    "Conversation",
    "Message",
    "Friendship",
    "UserFollow",
    "ModerationLog",
    "ModerationWord",
    "Notification",
    "AudioListenEvent",
    "PageView",
    "DailyStat",
    "AdminAuditLog",
    "AdminDailyMetric",
    "AdminPerformanceSnapshot",
    "PlatformAccessSetting",
    "PlatformAllowedEmail",
    "PlatformInvitation",
    "SiteFeedback",
    "EmailCampaign",
    "EmailOutbox",
    "AuthEmailCode",
]


# Delete stored media files when the rows that use them go away.
from app import media_cleanup as _media_cleanup  # noqa: E402

_media_cleanup.register()
