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
    author_audio_can_upload: bool = False
    author_audio_status: Optional[str] = None
    author_audio_message: Optional[str] = None



class PostAudioDeleteResponse(BaseModel):
    removed: int
    audio_available: bool
    audio_status: Optional[str] = None
    audio_source: Optional[str] = None
    audio_id: Optional[int] = None
    audio_playback_url: Optional[str] = None
    audio_tts_character_count: int = 0
    author_audio_status: Optional[str] = None
    author_audio_message: Optional[str] = None


class AudioTrack(BaseModel):
    audio_id: int
    post_id: int
    title: str
    slug: str
    author_id: Optional[int] = None
    author_username: str
    category: Optional[str] = None
    source: str
    playback_url: str
    content_type: Optional[str] = None
    duration_seconds: Optional[float] = None
    viewer_following: bool = False
    viewer_friendship_status: str = "none"
    viewer_friendship_id: Optional[int] = None



class SeriesAudioPlaylist(BaseModel):
    series_id: int
    title: str
    tracks: List[AudioTrack]


class AudioPlaylistCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return _trim_required_string(value, 120, "Titlul")


class AudioPlaylistUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return _trim_required_string(value, 120, "Titlul")


class AudioPlaylistAddPostRequest(BaseModel):
    post_id: int = Field(..., ge=1)


class AudioPlaylistSummary(BaseModel):
    id: int
    owner_id: int
    title: str
    item_count: int = 0
    created_at: datetime
    updated_at: datetime


class AudioPlaylistItem(BaseModel):
    id: int
    playlist_id: int
    post_id: int
    position: int
    title: str
    slug: str
    author_id: Optional[int] = None
    author_username: str
    category: Optional[str] = None
    audio_available: bool = False
    audio_id: Optional[int] = None
    playback_url: Optional[str] = None
    created_at: datetime


class AudioPlaylistDetail(AudioPlaylistSummary):
    items: List[AudioPlaylistItem] = Field(default_factory=list)


class AudioPlaylistList(BaseModel):
    playlists: List[AudioPlaylistSummary] = Field(default_factory=list)


class AudioPlaylistPlayback(BaseModel):
    playlist_id: int
    title: str
    tracks: List[AudioTrack] = Field(default_factory=list)



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
    context: Literal["player", "post"] = "post"


class AudioListenSecondsResponse(BaseModel):
    recorded: bool
    audio_id: int
    post_id: int
    seconds: int
    mode: Literal["poezie", "proza_scurta", "toate"]
    total_post_seconds: int
    total_author_seconds: int
    # Free accounts: seconds left today in the continuous player. None = unlimited / not applicable.
    player_seconds_remaining: Optional[int] = None


class AudioListenQuota(BaseModel):
    unlimited: bool
    limit_seconds: Optional[int] = None
    used_seconds: int = 0
    remaining_seconds: Optional[int] = None
