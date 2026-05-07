from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator, model_validator

from .common import *

class PostBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=TITLE_CHARACTER_LIMIT)
    content: str

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: str) -> str:
        return _sanitize_required_rich_text(value)


class PostCreate(PostBase):
    category: PostCategory
    ai_critic: bool = False
    draft_id: Optional[int] = Field(None, ge=1)

    @model_validator(mode="after")
    def validate_post_content_length(self):
        _validate_post_content_limit(self.category, self.content)
        return self


class PostUpdate(PostBase):
    category: PostCategory

    @model_validator(mode="after")
    def validate_post_content_length(self):
        _validate_post_content_limit(self.category, self.content)
        return self


class Post(PostBase):
    id: int
    user_id: int
    slug: str
    category: Optional[str] = None
    view_count: int = 0
    seconds_listened: int = 0
    moderation_status: Optional[str] = None
    moderation_reason: Optional[str] = None
    toxicity_score: Optional[float] = None
    super_likes_count: int = 0
    viewer_super_liked: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


PostReportReason = Literal["offensive", "plagiarism"]
PostReportStatus = Literal["open", "resolved", "dismissed"]
PostReportAction = Literal["dismiss", "reject_post", "delete_post"]


class PostReportCreate(BaseModel):
    reason_type: PostReportReason
    details: Optional[str] = Field(None, max_length=2000)
    evidence_url: Optional[str] = Field(None, max_length=1000)

    @field_validator("details", "evidence_url")
    @classmethod
    def trim_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class PostReportReview(BaseModel):
    action: PostReportAction
    reason: str = Field(..., min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Motivul este obligatoriu.")
        return trimmed


class PostReport(BaseModel):
    id: int
    post_id: Optional[int] = None
    reporter_user_id: int
    reason_type: PostReportReason
    details: Optional[str] = None
    evidence_url: Optional[str] = None
    post_title: Optional[str] = None
    post_slug: Optional[str] = None
    post_author: Optional[str] = None
    post_author_id: Optional[int] = None
    reporter_username: Optional[str] = None
    status: PostReportStatus
    reviewed_by: Optional[int] = None
    reviewer_username: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)



class PostDraftSave(BaseModel):
    title: str = Field(default="", max_length=TITLE_CHARACTER_LIMIT)
    content: str = ""
    category: PostCategory = "poezie"

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return (value or "").strip()

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: str) -> str:
        return _sanitize_draft_rich_text(value or "")

    @model_validator(mode="after")
    def validate_draft_content_length(self):
        _validate_post_content_limit(self.category, self.content)
        return self



class PostDraft(PostDraftSave):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)



class PostDraftList(BaseModel):
    drafts: List[PostDraft] = Field(default_factory=list)



class CommentBase(BaseModel):
    content: str
    author_name: Optional[str] = None
    author_email: Optional[EmailStr] = None

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: str) -> str:
        cleaned = _sanitize_required_rich_text(value)
        _validate_visible_text_limit(cleaned, COMMENT_CHARACTER_LIMIT, "Comentariul")
        return cleaned


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
