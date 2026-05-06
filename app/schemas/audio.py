from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator, model_validator

from .common import *

class PostAudioStatus(BaseModel):
    available: bool
    can_listen: bool
    requires_audio_tier: bool
    status: Optional[str] = None
    source: Optional[str] = None
    audio_id: Optional[int] = None
    playback_url: Optional[str] = None
    content_type: Optional[str] = None
    title: Optional[str] = None
    author_username: Optional[str] = None
    message: Optional[str] = None



class AudioTrack(BaseModel):
    audio_id: int
    post_id: int
    title: str
    slug: str
    author_username: str
    category: Optional[str] = None
    source: str
    playback_url: str
    content_type: Optional[str] = None
    duration_seconds: Optional[float] = None



class SeriesAudioPlaylist(BaseModel):
    series_id: int
    title: str
    tracks: List[AudioTrack]



class AudioConversionQuota(BaseModel):
    premium_tier: str
    limit: int
    used: int
    remaining: int
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    can_request: bool



class TTSConversionRequest(BaseModel):
    post_ids: List[int]



class TTSConversionItem(BaseModel):
    post_id: int
    title: str
    status: str
    audio_id: int
    character_count: int



class TTSConversionResponse(BaseModel):
    queued: List[TTSConversionItem]
    skipped: List[TTSConversionItem]
    quota: AudioConversionQuota


class AudioListenSecondsRequest(BaseModel):
    event_id: str = Field(..., min_length=1, max_length=64)
    audio_id: int = Field(..., ge=1)
    seconds: int = Field(..., ge=1, le=60)
    mode: Literal["poezie", "proza_scurta", "toate"] = "toate"


class AudioListenSecondsResponse(BaseModel):
    recorded: bool
    audio_id: int
    post_id: int
    seconds: int
    mode: Literal["poezie", "proza_scurta", "toate"]
    total_post_seconds: int
    total_author_seconds: int
