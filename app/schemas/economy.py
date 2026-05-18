from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator, model_validator

from .common import *

ShopItemSlot = Literal["profile_badge", "costume", "frame", "background", "title"]

class ShopItemBase(BaseModel):
    slug: str = Field(..., min_length=1, max_length=120, pattern=r"^[a-z0-9-]+$")
    name: str = Field(..., min_length=1, max_length=180)
    description: Optional[str] = Field(None, max_length=2000)
    price: int = Field(..., ge=0)
    slot: ShopItemSlot = "profile_badge"
    asset_url: Optional[str] = Field(None, max_length=500)
    is_active: bool = True
    sort_order: int = 0



class ShopItemCreate(ShopItemBase):
    pass



class ShopItemUpdate(BaseModel):
    slug: Optional[str] = Field(None, min_length=1, max_length=120, pattern=r"^[a-z0-9-]+$")
    name: Optional[str] = Field(None, min_length=1, max_length=180)
    description: Optional[str] = Field(None, max_length=2000)
    price: Optional[int] = Field(None, ge=0)
    slot: Optional[ShopItemSlot] = None
    asset_url: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None



class ShopItemOut(ShopItemBase):
    id: int
    owned: bool = False
    equipped: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)



class InventoryItemOut(BaseModel):
    id: int
    item: ShopItemOut
    purchased_at: datetime

    model_config = ConfigDict(from_attributes=True)



class EquippedItemOut(BaseModel):
    id: int
    slot: str
    item: ShopItemOut
    equipped_at: datetime

    model_config = ConfigDict(from_attributes=True)



class ShopState(BaseModel):
    balance: int
    items: List[ShopItemOut]
    inventory: List[InventoryItemOut] = Field(default_factory=list)
    equipped: List[EquippedItemOut] = Field(default_factory=list)



class EquipItemRequest(BaseModel):
    item_id: int


class GologaniTransactionOut(BaseModel):
    id: int
    user_id: int
    amount: int
    balance_after: int
    event_type: str
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ===================================
# FORUM SCHEMAS
# ===================================

ForumSection = Literal["anunturi", "general", "poezie", "proza_scurta"]
ForumModerationStatus = Literal["pending", "approved", "flagged", "rejected"]

