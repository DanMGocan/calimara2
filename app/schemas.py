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
