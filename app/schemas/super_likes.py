from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator, model_validator

from .common import *

class SuperLike(BaseModel):
    id: int
    post_id: int
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SuperLikeQuota(BaseModel):
    premium_tier: str
    monthly_quota: int
    used_this_month: int
    remaining: int
    period_start: datetime
    period_end: datetime
    month_resets_at: datetime
    # Compatibility aliases retained for older API clients.
    weekly_quota: int
    used_this_week: int
    week_resets_at: datetime
    is_premium: bool


# ===================================
# PREMIUM / STRIPE SCHEMAS
# ===================================
