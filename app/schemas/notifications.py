from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator, model_validator

from .common import *

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

    model_config = ConfigDict(from_attributes=True)

# ===================================
# GOLOGANI / SHOP SCHEMAS
# ===================================

ShopItemSlot = Literal["profile_badge", "costume", "frame", "background", "title"]


