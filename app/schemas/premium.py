from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator, model_validator

from .common import *

PaidPremiumTierKey = Literal["trubadur", "cronicar", "rapsod"]
PremiumTierKey = Literal["free", "trubadur", "cronicar", "rapsod"]


class PremiumPlan(BaseModel):
    key: PremiumTierKey
    name: str
    eyebrow: str
    price: str
    cadence: str
    summary: str
    benefits: List[str]
    available: bool


class PremiumCheckoutResponse(BaseModel):
    url: str



class PremiumCheckoutRequest(BaseModel):
    tier: PaidPremiumTierKey = "trubadur"



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
