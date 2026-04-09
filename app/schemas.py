from pydantic import BaseModel, EmailStr, validator, Field
from datetime import datetime
from typing import Optional, List

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

class GoogleUserInfo(BaseModel):
    google_id: str
    email: str
    name: str
    picture: Optional[str] = None

class UserInDB(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SocialLinksUpdate(BaseModel):
    facebook_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    instagram_url: Optional[str] = None
    x_url: Optional[str] = None
    bluesky_url: Optional[str] = None
    buymeacoffee_url: Optional[str] = None

class TagBase(BaseModel):
    tag_name: str = Field(..., max_length=12, description="Tag name (max 12 characters)")

class Tag(TagBase):
    id: int
    post_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class PostBase(BaseModel):
    title: str
    content: str
    category: Optional[str] = None # Category key
    tags: Optional[List[str]] = Field(default=[], max_items=6, description="List of tags (max 6)")

class PostCreate(PostBase):
    @validator('tags', pre=True, each_item=True)
    def validate_tag_length(cls, v):
        if len(v) > 12:
            raise ValueError('Tag must be at most 12 characters long')
        return v

class PostUpdate(PostBase):
    pass

class Post(PostBase):
    id: int
    user_id: int
    slug: str
    view_count: int = 0
    moderation_status: Optional[str] = None
    moderation_reason: Optional[str] = None
    toxicity_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    tags: List[Tag] = []

    class Config:
        from_attributes = True

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
    moderation_status: Optional[str] = None
    moderation_reason: Optional[str] = None
    toxicity_score: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True

class Like(BaseModel):
    id: int
    post_id: int
    user_id: Optional[int] = None
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ===================================
# MESSAGE SCHEMAS
# ===================================

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class MessageToUser(BaseModel):
    recipient_username: str
    content: str = Field(..., min_length=1, max_length=2000)

class MessageBase(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    content: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class Message(MessageBase):
    sender: Optional[UserBase] = None

class ConversationBase(BaseModel):
    id: int
    user1_id: int
    user2_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

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

    class Config:
        from_attributes = True

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
# DRAMA SCHEMAS
# ===================================

class DramaCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    character_name: str = Field(..., min_length=1, max_length=100)
    character_description: Optional[str] = None

class DramaUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    is_open_for_applications: Optional[bool] = None

class DramaCharacterResponse(BaseModel):
    id: int
    drama_id: int
    user_id: int
    character_name: str
    character_description: Optional[str] = None
    is_creator: bool
    joined_at: datetime
    username: Optional[str] = None
    avatar_seed: Optional[str] = None

    class Config:
        from_attributes = True

class DramaReplyResponse(BaseModel):
    id: int
    act_id: int
    character_id: int
    content: str
    stage_direction: Optional[str] = None
    position: int
    created_at: datetime
    character_name: Optional[str] = None
    username: Optional[str] = None

    class Config:
        from_attributes = True

class DramaActResponse(BaseModel):
    id: int
    drama_id: int
    act_number: int
    title: str
    setting: Optional[str] = None
    status: str
    created_at: datetime
    replies: List[DramaReplyResponse] = []

    class Config:
        from_attributes = True

class DramaResponse(BaseModel):
    id: int
    user_id: int
    title: str
    slug: str
    description: Optional[str] = None
    status: str
    is_open_for_applications: bool
    view_count: int
    likes_count: int = 0
    created_at: datetime
    updated_at: datetime
    owner_username: Optional[str] = None
    owner_avatar_seed: Optional[str] = None
    characters: List[DramaCharacterResponse] = []
    acts: List[DramaActResponse] = []

    class Config:
        from_attributes = True

class ActCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    setting: Optional[str] = None

class ActUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    setting: Optional[str] = None

class ReplyCreate(BaseModel):
    content: str = Field(..., min_length=1)
    stage_direction: Optional[str] = Field(None, max_length=500)

class ReplyUpdate(BaseModel):
    content: Optional[str] = None
    stage_direction: Optional[str] = Field(None, max_length=500)

class ReplyReorder(BaseModel):
    reply_ids: List[int]

class InvitationCreate(BaseModel):
    to_username: str
    character_name: Optional[str] = Field(None, max_length=100)
    message: Optional[str] = None

class ApplicationCreate(BaseModel):
    character_name: str = Field(..., min_length=1, max_length=100)
    character_description: Optional[str] = None
    message: Optional[str] = None

class InvitationRespond(BaseModel):
    status: str = Field(..., pattern="^(accepted|rejected)$")

class DramaCommentCreate(BaseModel):
    content: str = Field(..., min_length=1)
    author_name: Optional[str] = None

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

    class Config:
        from_attributes = True
