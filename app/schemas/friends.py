from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


FriendshipStatus = Literal["none", "self", "outgoing_pending", "incoming_pending", "friends"]


class FriendUserRef(BaseModel):
    id: int
    username: str
    subtitle: Optional[str] = None
    avatar_seed: Optional[str] = None
    avatar_url: Optional[str] = None


class FriendshipOut(BaseModel):
    id: int
    status: str
    direction: Optional[str] = None
    requested_by_id: int
    user: FriendUserRef
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
