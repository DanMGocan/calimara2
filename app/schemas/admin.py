from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator, model_validator

from .common import *

AdminPremiumTier = Literal["free", "trubadur", "cronicar", "rapsod"]
AdminContentType = Literal["post", "comment", "audio", "forum_thread", "forum_reply"]
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


AdminContentType = Literal["post", "comment", "audio", "forum_thread", "forum_reply"]
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
