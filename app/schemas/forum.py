from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator, model_validator

from .common import *

ForumSection = Literal["anunturi", "general", "poezie", "proza_scurta"]
ForumModerationStatus = Literal["pending", "approved", "flagged", "rejected"]

class ForumAuthorRef(BaseModel):
    id: int
    username: str
    avatar_seed: Optional[str] = None
    avatar_url: Optional[str] = None
    profile_photo_url: Optional[str] = None
    is_premium: bool = False
    premium_tier: str = "free"
    gologani_balance: int = 0
    forum_post_count: int = 0
    published_post_count: int = 0

    model_config = ConfigDict(from_attributes=True)



class ForumThreadCreate(BaseModel):
    section: ForumSection
    title: str = Field(..., min_length=1, max_length=TITLE_CHARACTER_LIMIT)
    content: str = Field(..., min_length=1, max_length=8000)

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return _trim_required_string(value, TITLE_CHARACTER_LIMIT, "Titlul")

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: str) -> str:
        return _sanitize_required_rich_text(value)



class ForumReplyCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: str) -> str:
        return _sanitize_required_rich_text(value)



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
# SERIES SCHEMAS
# ===================================
