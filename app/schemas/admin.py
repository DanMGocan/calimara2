from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator, model_validator

from .. import rich_text
from .common import *

AdminPremiumTier = Literal["free", "trubadur", "cronicar", "rapsod"]
AdminContentType = Literal["post", "comment", "audio", "forum_thread", "forum_reply", "theatre_entry", "stafeta_segment"]
AdminModerationStatus = Literal["approved", "pending", "flagged", "rejected"]

class ModerationActionRequest(BaseModel):
    action: str
    reason: str = ""


class SuspendUserRequest(BaseModel):
    reason: str



class AdminReasonRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)



class AdminRoleUpdate(BaseModel):
    is_admin: bool
    is_moderator: bool
    reason: str = Field(..., min_length=1, max_length=1000)


AdminPremiumTier = Literal["free", "trubadur", "cronicar", "rapsod"]



class AdminPremiumUpdate(BaseModel):
    premium_tier: AdminPremiumTier
    premium_until: Optional[datetime] = None
    premium_period_start: Optional[datetime] = None
    stripe_subscription_id: Optional[str] = Field(None, max_length=100)
    reason: str = Field(..., min_length=1, max_length=1000)



class AdminGologaniAdjustment(BaseModel):
    amount: int = Field(..., ge=-1000000, le=1000000)
    reason: str = Field(..., min_length=1, max_length=1000)

    @field_validator("amount")
    @classmethod
    def amount_must_not_be_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("Suma trebuie să fie diferită de zero")
        return value


class AdminPlatformAccessUpdate(BaseModel):
    open: bool


class AdminPlatformAllowedEmailCreate(BaseModel):
    email: EmailStr
    note: Optional[str] = Field(None, max_length=500)


class AdminEmailAudience(BaseModel):
    q: str = Field("", max_length=255)
    role: Literal["all", "admin", "moderator", "member"] = "all"
    status: Literal["all", "active", "suspended"] = "active"
    premium: AdminPremiumTier | Literal["all"] = "all"
    joined_from: Optional[str] = None
    joined_to: Optional[str] = None
    last_login_from: Optional[str] = None
    last_login_to: Optional[str] = None
    min_posts: Optional[int] = Field(None, ge=0)
    max_posts: Optional[int] = Field(None, ge=0)
    selected_user_ids: List[int] = Field(default_factory=list, max_length=5000)

    @model_validator(mode="after")
    def validate_post_range(self):
        if self.min_posts is not None and self.max_posts is not None and self.min_posts > self.max_posts:
            raise ValueError("Numărul minim de postări nu poate depăși maximul.")
        return self


class AdminEmailPreviewRequest(BaseModel):
    audience: AdminEmailAudience = Field(default_factory=AdminEmailAudience)


class AdminEmailCampaignCreate(BaseModel):
    audience: AdminEmailAudience = Field(default_factory=AdminEmailAudience)
    subject: str = Field(..., min_length=1, max_length=255)
    html_content: str = Field(..., min_length=1, max_length=200000)

    @field_validator("html_content")
    @classmethod
    def html_must_have_text(cls, value: str) -> str:
        if not rich_text.rich_text_to_plain_text(value):
            raise ValueError("Emailul trebuie să conțină text.")
        return value


AdminContentType = Literal["post", "comment", "audio", "forum_thread", "forum_reply", "theatre_entry", "stafeta_segment"]
AdminModerationStatus = Literal["approved", "pending", "flagged", "rejected"]



class AdminContentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=160)
    content: Optional[str] = None
    category: Optional[PostCategory] = None
    section: Optional[Literal["general", "poezie", "proza_scurta", "feedback", "anunturi"]] = None
    moderation_status: Optional[AdminModerationStatus] = None
    reason: str = Field(..., min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def sanitize_optional_content(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _sanitize_required_rich_text(value)

# ===================================
# NOTIFICATION SCHEMAS
# ===================================
