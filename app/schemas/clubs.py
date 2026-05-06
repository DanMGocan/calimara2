from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator, model_validator

from .common import *

ClubSpeciality = str  # "poezie" | "proza_scurta"
ClubMemberRole = str  # "owner" | "admin" | "member"

class ClubOwnerRef(BaseModel):
    id: int
    username: str
    avatar_seed: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ClubMemberRef(BaseModel):
    id: int
    user_id: int
    username: str
    avatar_seed: Optional[str] = None
    role: str
    joined_at: datetime
    contribution_count: int = 0



class ClubCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    speciality: str = Field(..., pattern=r"^(poezie|proza_scurta)$")
    description: Optional[str] = Field(None, max_length=2000)
    motto: Optional[str] = Field(None, max_length=200)
    theme: Optional[str] = Field(None, max_length=200)
    avatar_seed: Optional[str] = Field(None, max_length=100)



class ClubUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=120)
    speciality: Optional[str] = Field(None, pattern=r"^(poezie|proza_scurta)$")
    description: Optional[str] = Field(None, max_length=2000)
    motto: Optional[str] = Field(None, max_length=200)
    theme: Optional[str] = Field(None, max_length=200)
    avatar_seed: Optional[str] = Field(None, max_length=100)



class ClubFeaturedRef(BaseModel):
    post_id: int
    post_title: str
    post_slug: str
    post_author: Optional[ClubOwnerRef] = None
    featured_until: datetime



class ClubBoardMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    parent_id: Optional[int] = None



class ClubBoardAuthorRef(BaseModel):
    id: int
    username: str
    avatar_seed: Optional[str] = None
    role: Optional[str] = None  # member role within the club, if known



class ClubBoardMessageOut(BaseModel):
    id: int
    club_id: int
    parent_id: Optional[int] = None
    content: str
    created_at: datetime
    updated_at: datetime
    author: Optional[ClubBoardAuthorRef] = None
    replies: List["ClubBoardMessageOut"] = Field(default_factory=list)


ClubBoardMessageOut.model_rebuild()



class ClubSummary(BaseModel):
    id: int
    owner_id: int
    title: str
    slug: str
    description: Optional[str] = None
    motto: Optional[str] = None
    avatar_seed: Optional[str] = None
    theme: Optional[str] = None
    speciality: str
    member_count: int = 0
    owner: Optional[ClubOwnerRef] = None
    created_at: datetime
    updated_at: datetime



class ClubDetail(ClubSummary):
    members: List[ClubMemberRef] = Field(default_factory=list)
    featured: Optional[ClubFeaturedRef] = None
    recent_messages: List[ClubBoardMessageOut] = Field(default_factory=list)
    my_role: Optional[str] = None
    my_pending_request_status: Optional[str] = None
    pending_request_count: Optional[int] = None  # only populated for owner/admin



class ClubInviteRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)



class ClubJoinRespondRequest(BaseModel):
    action: str = Field(..., pattern=r"^(approve|reject)$")



class ClubMemberRoleUpdate(BaseModel):
    role: str = Field(..., pattern=r"^(admin|member)$")



class ClubFeaturedSetRequest(BaseModel):
    post_id: int



class ClubJoinRequestOut(BaseModel):
    id: int
    club_id: int
    user: ClubOwnerRef
    direction: str
    status: str
    initiator_id: int
    created_at: datetime
    responded_at: Optional[datetime] = None



class ClubPendingItem(BaseModel):
    request: ClubJoinRequestOut
    club: ClubSummary
    direction: str  # mirrors request.direction for convenience


# ===================================
# SUPER-APRECIEZ SCHEMAS
# ===================================


ClubBoardMessageOut.model_rebuild()
