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
    weekly_quota: int
    used_this_week: int
    remaining: int
    week_resets_at: datetime
    is_premium: bool


# ===================================
# PREMIUM / STRIPE SCHEMAS
# ===================================

