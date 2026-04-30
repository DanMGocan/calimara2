from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field
from datetime import datetime
from typing import Literal, Optional, List

class UserBase(BaseModel):
    username: str
    email: EmailStr
    google_id: str
    subtitle: Optional[str] = None # User motto
    avatar_seed: Optional[str] = None # DiceBear avatar seed
    
    # Social media links
    facebook_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    instagram_url: Optional[str] = None
    x_url: Optional[str] = None
    bluesky_url: Optional[str] = None
    
    # Donation/support links
    patreon_url: Optional[str] = None
    paypal_url: Optional[str] = None
    buymeacoffee_url: Optional[str] = None

class UserSetup(BaseModel):
    username: str
    subtitle: Optional[str] = None
    avatar_seed: str

class UserProfileUpdate(BaseModel):
    subtitle: Optional[str] = None
    avatar_seed: Optional[str] = None

class GoogleUserInfo(BaseModel):
    google_id: str
    email: str
    name: str
    picture: Optional[str] = None

class UserInDB(UserBase):
    id: int
    is_premium: bool = False
    has_audio_access: bool = False
    has_author_audio_access: bool = False
    premium_tier: str = "free"
    premium_period_start: Optional[datetime] = None
    premium_until: Optional[datetime] = None
    gologani_balance: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
class SocialLinksUpdate(BaseModel):
    facebook_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    instagram_url: Optional[str] = None
    x_url: Optional[str] = None
    bluesky_url: Optional[str] = None
    buymeacoffee_url: Optional[str] = None

class PostBase(BaseModel):
    title: str
    content: str

class PostCreate(PostBase):
    ai_critic: bool = False

class PostUpdate(PostBase):
    pass

class Post(PostBase):
    id: int
    user_id: int
    slug: str
    category: Optional[str] = None
    view_count: int = 0
    moderation_status: Optional[str] = None
    moderation_reason: Optional[str] = None
    toxicity_score: Optional[float] = None
    super_likes_count: int = 0
    viewer_super_liked: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
class CommentBase(BaseModel):
    content: str
    author_name: Optional[str] = None
    author_email: Optional[EmailStr] = None

class CommentCreate(CommentBase):
    pass

class Comment(CommentBase):
    id: int
    post_id: int
    user_id: Optional[int] = None
    approved: bool
    is_robot: bool = False
    moderation_status: Optional[str] = None
    moderation_reason: Optional[str] = None
    toxicity_score: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

DiacriticsKind = Literal["post", "forum_thread", "forum_reply", "comment"]


class DiacriticsRequest(BaseModel):
    kind: DiacriticsKind
    title: Optional[str] = Field(None, max_length=300)
    content: str = Field(..., min_length=1, max_length=12000)


class DiacriticsResponse(BaseModel):
    title: Optional[str] = None
    content: str
    changed: bool = False


class Like(BaseModel):
    id: int
    post_id: int
    user_id: Optional[int] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
# ===================================
# MESSAGE SCHEMAS
# ===================================

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class MessageToUser(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recipient_username: str = Field(
        validation_alias=AliasChoices("recipient_username", "username")
    )
    content: str = Field(..., min_length=1, max_length=2000)

class MessageBase(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    content: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
class Message(MessageBase):
    sender: Optional[UserBase] = None

class ConversationBase(BaseModel):
    id: int
    user1_id: int
    user2_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
class Conversation(ConversationBase):
    user1: Optional[UserBase] = None
    user2: Optional[UserBase] = None
    messages: List[Message] = []
    
class ConversationSummary(BaseModel):
    id: int
    other_user: UserBase
    latest_message: Optional[MessageBase] = None
    unread_count: int = 0
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
# ===================================
# MODERATION & ADMIN SCHEMAS
# ===================================

class BestFriendsUpdate(BaseModel):
    friends: List[str] = Field(default=[], max_length=3, description="List of friend usernames (max 3)")

class FeaturedPostsUpdate(BaseModel):
    post_ids: List[Optional[int]] = Field(default=[], max_length=3, description="List of post IDs (max 3)")

class ModerationActionRequest(BaseModel):
    action: str
    reason: str = ""

class SuspendUserRequest(BaseModel):
    reason: str

# ===================================
# NOTIFICATION SCHEMAS
# ===================================

class NotificationResponse(BaseModel):
    id: int
    user_id: int
    type: str
    title: str
    message: Optional[str] = None
    link: Optional[str] = None
    is_read: bool
    metadata: Optional[dict] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ===================================
# GOLOGANI / SHOP SCHEMAS
# ===================================

ShopItemSlot = Literal["profile_badge", "costume", "frame", "background", "title"]


class ShopItemBase(BaseModel):
    slug: str = Field(..., min_length=1, max_length=120, pattern=r"^[a-z0-9-]+$")
    name: str = Field(..., min_length=1, max_length=180)
    description: Optional[str] = Field(None, max_length=2000)
    price: int = Field(..., ge=0)
    slot: ShopItemSlot = "profile_badge"
    asset_url: Optional[str] = Field(None, max_length=500)
    is_active: bool = True
    sort_order: int = 0


class ShopItemCreate(ShopItemBase):
    pass


class ShopItemUpdate(BaseModel):
    slug: Optional[str] = Field(None, min_length=1, max_length=120, pattern=r"^[a-z0-9-]+$")
    name: Optional[str] = Field(None, min_length=1, max_length=180)
    description: Optional[str] = Field(None, max_length=2000)
    price: Optional[int] = Field(None, ge=0)
    slot: Optional[ShopItemSlot] = None
    asset_url: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class ShopItemOut(ShopItemBase):
    id: int
    owned: bool = False
    equipped: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InventoryItemOut(BaseModel):
    id: int
    item: ShopItemOut
    purchased_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EquippedItemOut(BaseModel):
    id: int
    slot: str
    item: ShopItemOut
    equipped_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ShopState(BaseModel):
    balance: int
    items: List[ShopItemOut]
    inventory: List[InventoryItemOut] = []
    equipped: List[EquippedItemOut] = []


class EquipItemRequest(BaseModel):
    item_id: int

class GologaniTransactionOut(BaseModel):
    id: int
    user_id: int
    amount: int
    balance_after: int
    event_type: str
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ===================================
# FORUM SCHEMAS
# ===================================

ForumSection = Literal["general", "poezie", "proza_scurta", "feedback", "anunturi"]
ForumModerationStatus = Literal["pending", "approved", "flagged", "rejected"]


class ForumAuthorRef(BaseModel):
    id: int
    username: str
    avatar_seed: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ForumThreadCreate(BaseModel):
    section: ForumSection
    title: str = Field(..., min_length=1, max_length=160)
    content: str = Field(..., min_length=1, max_length=8000)


class ForumReplyCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


class ForumThreadModerationAction(BaseModel):
    action: Literal["lock", "unlock", "pin", "unpin"]


class ForumThreadSummary(BaseModel):
    id: int
    section: ForumSection
    title: str
    slug: str
    author: Optional[ForumAuthorRef] = None
    reply_count: int = 0
    view_count: int = 0
    is_locked: bool
    is_pinned: bool
    moderation_status: ForumModerationStatus
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ForumReplyOut(BaseModel):
    id: int
    thread_id: int
    content: str
    author: Optional[ForumAuthorRef] = None
    moderation_status: ForumModerationStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ForumThreadDetail(ForumThreadSummary):
    content: str
    moderation_reason: Optional[str] = None
    replies: List[ForumReplyOut] = Field(default_factory=list)
# ===================================
# COLLECTION SCHEMAS
# ===================================

class CollectionAuthor(BaseModel):
    id: int
    username: str
    avatar_seed: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
class CollectionCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=2000)

class CollectionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=2000)

class CollectionSummary(BaseModel):
    id: int
    owner_id: int
    title: str
    slug: str
    description: Optional[str] = None
    owner: Optional[CollectionAuthor] = None
    post_count: int = 0
    pending_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
class CollectionPostPostRef(BaseModel):
    """Subset of Post info needed for collection listings."""
    id: int
    title: str
    slug: str
    category: Optional[str] = None
    owner: Optional[CollectionAuthor] = None

    model_config = ConfigDict(from_attributes=True)
class CollectionPostEntry(BaseModel):
    id: int
    collection_id: int
    post_id: int
    initiator_id: int
    status: str
    position: Optional[int] = None
    created_at: datetime
    responded_at: Optional[datetime] = None
    post: Optional[CollectionPostPostRef] = None

    model_config = ConfigDict(from_attributes=True)
class CollectionDetail(CollectionSummary):
    posts: List[CollectionPostEntry] = []

class CollectionAddPostRequest(BaseModel):
    post_id: int

class CollectionRespondRequest(BaseModel):
    action: str  # "accept" | "reject"

class PendingApprovalItem(BaseModel):
    entry: CollectionPostEntry
    direction: str  # "invitation" (owner invited author) | "suggestion" (author suggested to owner)
    collection: CollectionSummary
    post: CollectionPostPostRef

class CollectionMembershipRef(BaseModel):
    id: int
    title: str
    slug: str
    owner: CollectionAuthor

    model_config = ConfigDict(from_attributes=True)
# ===================================
# CLUB SCHEMAS
# ===================================

# Allowed values mirror Post.category so featured-post enforcement is symmetric.
ClubSpeciality = str  # "poezie" | "proza_scurta"
ClubMemberRole = str  # "owner" | "admin" | "member"


class ClubOwnerRef(BaseModel):
    id: int
    username: str
    avatar_seed: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
class ClubMemberRef(BaseModel):
    id: int
    user_id: int
    username: str
    avatar_seed: Optional[str] = None
    role: str
    joined_at: datetime
    contribution_count: int = 0


class ClubCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    speciality: str = Field(..., pattern=r"^(poezie|proza_scurta)$")
    description: Optional[str] = Field(None, max_length=2000)
    motto: Optional[str] = Field(None, max_length=200)
    theme: Optional[str] = Field(None, max_length=200)
    avatar_seed: Optional[str] = Field(None, max_length=100)


class ClubUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=120)
    speciality: Optional[str] = Field(None, pattern=r"^(poezie|proza_scurta)$")
    description: Optional[str] = Field(None, max_length=2000)
    motto: Optional[str] = Field(None, max_length=200)
    theme: Optional[str] = Field(None, max_length=200)
    avatar_seed: Optional[str] = Field(None, max_length=100)


class ClubFeaturedRef(BaseModel):
    post_id: int
    post_title: str
    post_slug: str
    post_author: Optional[ClubOwnerRef] = None
    featured_until: datetime


class ClubBoardMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    parent_id: Optional[int] = None


class ClubBoardAuthorRef(BaseModel):
    id: int
    username: str
    avatar_seed: Optional[str] = None
    role: Optional[str] = None  # member role within the club, if known


class ClubBoardMessageOut(BaseModel):
    id: int
    club_id: int
    parent_id: Optional[int] = None
    content: str
    created_at: datetime
    updated_at: datetime
    author: Optional[ClubBoardAuthorRef] = None
    replies: List["ClubBoardMessageOut"] = []


ClubBoardMessageOut.model_rebuild()


class ClubSummary(BaseModel):
    id: int
    owner_id: int
    title: str
    slug: str
    description: Optional[str] = None
    motto: Optional[str] = None
    avatar_seed: Optional[str] = None
    theme: Optional[str] = None
    speciality: str
    member_count: int = 0
    owner: Optional[ClubOwnerRef] = None
    created_at: datetime
    updated_at: datetime


class ClubDetail(ClubSummary):
    members: List[ClubMemberRef] = []
    featured: Optional[ClubFeaturedRef] = None
    recent_messages: List[ClubBoardMessageOut] = []
    my_role: Optional[str] = None
    my_pending_request_status: Optional[str] = None
    pending_request_count: Optional[int] = None  # only populated for owner/admin


class ClubInviteRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)


class ClubJoinRespondRequest(BaseModel):
    action: str = Field(..., pattern=r"^(approve|reject)$")


class ClubMemberRoleUpdate(BaseModel):
    role: str = Field(..., pattern=r"^(admin|member)$")


class ClubFeaturedSetRequest(BaseModel):
    post_id: int


class ClubJoinRequestOut(BaseModel):
    id: int
    club_id: int
    user: ClubOwnerRef
    direction: str
    status: str
    initiator_id: int
    created_at: datetime
    responded_at: Optional[datetime] = None


class ClubPendingItem(BaseModel):
    request: ClubJoinRequestOut
    club: ClubSummary
    direction: str  # mirrors request.direction for convenience


# ===================================
# SUPER-APRECIEZ SCHEMAS
# ===================================

class SuperLike(BaseModel):
    id: int
    post_id: int
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
class SuperLikeQuota(BaseModel):
    weekly_quota: int
    used_this_week: int
    remaining: int
    week_resets_at: datetime
    is_premium: bool


# ===================================
# PREMIUM / STRIPE SCHEMAS
# ===================================

class PremiumCheckoutResponse(BaseModel):
    url: str


class PremiumCheckoutRequest(BaseModel):
    tier: Literal["premium", "audio", "author_audio"] = "premium"


class PremiumPortalResponse(BaseModel):
    url: str


class PremiumStatus(BaseModel):
    is_premium: bool
    has_audio_access: bool = False
    has_author_audio_access: bool = False
    premium_tier: str = "free"
    premium_period_start: Optional[datetime] = None
    premium_until: Optional[datetime] = None
    has_stripe_customer: bool
    has_active_subscription: bool


# ===================================
# AUDIO SCHEMAS
# ===================================

class PostAudioStatus(BaseModel):
    available: bool
    can_listen: bool
    requires_audio_tier: bool
    status: Optional[str] = None
    source: Optional[str] = None
    audio_id: Optional[int] = None
    playback_url: Optional[str] = None
    content_type: Optional[str] = None
    title: Optional[str] = None
    author_username: Optional[str] = None
    message: Optional[str] = None


class AudioTrack(BaseModel):
    audio_id: int
    post_id: int
    title: str
    slug: str
    author_username: str
    source: str
    playback_url: str
    content_type: Optional[str] = None


class CollectionAudioPlaylist(BaseModel):
    collection_id: int
    title: str
    tracks: List[AudioTrack]


class AudioConversionQuota(BaseModel):
    premium_tier: str
    limit: int
    used: int
    remaining: int
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    can_request: bool


class TTSConversionRequest(BaseModel):
    post_ids: List[int]


class TTSConversionItem(BaseModel):
    post_id: int
    title: str
    status: str
    audio_id: int
    character_count: int


class TTSConversionResponse(BaseModel):
    queued: List[TTSConversionItem]
    skipped: List[TTSConversionItem]
    quota: AudioConversionQuota
