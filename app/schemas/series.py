from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator, model_validator

from .common import *

class SeriesAuthor(BaseModel):
    id: int
    username: str
    avatar_seed: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)



class SeriesCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=2000)



class SeriesUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=2000)



class SeriesSummary(BaseModel):
    id: int
    owner_id: int
    title: str
    slug: str
    description: Optional[str] = None
    owner: Optional[SeriesAuthor] = None
    post_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)



class SeriesPostPostRef(BaseModel):
    """Subset of Post info needed for series listings."""
    id: int
    title: str
    slug: str
    category: Optional[str] = None
    moderation_status: Optional[str] = None
    owner: Optional[SeriesAuthor] = None

    model_config = ConfigDict(from_attributes=True)



class SeriesPostEntry(BaseModel):
    id: int
    series_id: int
    post_id: int
    position: int
    created_at: datetime
    post: Optional[SeriesPostPostRef] = None

    model_config = ConfigDict(from_attributes=True)



class SeriesDetail(SeriesSummary):
    posts: List[SeriesPostEntry] = Field(default_factory=list)



class SeriesAddPostRequest(BaseModel):
    post_id: int



class SeriesReorderRequest(BaseModel):
    post_ids: List[int] = Field(..., min_length=1)



class SeriesMembershipRef(BaseModel):
    id: int
    title: str
    slug: str
    owner: SeriesAuthor

    model_config = ConfigDict(from_attributes=True)
# ===================================
# CLUB SCHEMAS
# ===================================

# Allowed values mirror Post.category so featured-post enforcement is symmetric.
ClubSpeciality = str  # "poezie" | "proza_scurta"
ClubMemberRole = str  # "owner" | "admin" | "member"


