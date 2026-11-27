from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator, model_validator

from .common import *

# Sections are admin-managed rows (forum_sections); threads store the section slug.
ForumSection = str
FORUM_SECTION_SLUG_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,59}$"
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
    section: ForumSection = Field(..., min_length=1, max_length=60)
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
    action: Literal["lock", "unlock", "pin", "unpin", "move"]
    section: Optional[str] = Field(None, max_length=60)



class ForumReplyModerationAction(BaseModel):
    action: Literal["pin", "unpin"]



def _clean_section_text(value: Optional[str], limit: int, label: str, required: bool) -> Optional[str]:
    if value is None:
        if required:
            raise ValueError(f"{label} este obligatoriu")
        return None
    cleaned = " ".join(str(value).split())
    if not cleaned:
        if required:
            raise ValueError(f"{label} este obligatoriu")
        return None
    if len(cleaned) > limit:
        raise ValueError(f"{label} poate avea cel mult {limit} caractere")
    return cleaned



class ForumSectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    slug: Optional[str] = Field(None, max_length=60, pattern=FORUM_SECTION_SLUG_PATTERN)
    description: Optional[str] = Field(None, max_length=300)
    staff_only: bool = False
    is_featured: bool = False
    is_archived: bool = False

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _clean_section_text(value, 80, "Numele", required=True)

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        return _clean_section_text(value, 300, "Descrierea", required=False)

    @field_validator("slug", mode="before")
    @classmethod
    def normalize_slug(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip().lower()
        return cleaned or None



class ForumSectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    slug: Optional[str] = Field(None, max_length=60, pattern=FORUM_SECTION_SLUG_PATTERN)
    description: Optional[str] = Field(None, max_length=300)
    staff_only: Optional[bool] = None
    is_featured: Optional[bool] = None
    is_archived: Optional[bool] = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _clean_section_text(value, 80, "Numele", required=True)

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        # An explicit empty string clears the description.
        if value is None:
            return None
        return _clean_section_text(value, 300, "Descrierea", required=False) or ""

    @field_validator("slug", mode="before")
    @classmethod
    def normalize_slug(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip().lower()
        return cleaned or None



class ForumSectionOrder(BaseModel):
    section_ids: List[int] = Field(..., min_length=1, max_length=200)



class AdminForumThreadBulkAction(BaseModel):
    thread_ids: List[int] = Field(..., min_length=1, max_length=200)
    action: Literal["pin", "unpin", "lock", "unlock", "move", "delete"]
    section: Optional[str] = Field(None, max_length=60)



class ForumThreadSummary(BaseModel):
    id: int
    section: ForumSection
    section_label: Optional[str] = None
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
