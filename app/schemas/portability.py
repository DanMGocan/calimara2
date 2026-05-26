from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .common import PostCategory, _sanitize_required_rich_text, _sanitize_optional_profile_text, _trim_optional_string, _trim_required_string


class DataPortabilityProfile(BaseModel):
    subtitle: Optional[str] = None
    avatar_seed: Optional[str] = None
    cover_seed: Optional[str] = None
    location: Optional[str] = None
    youtube_playlist_url: Optional[str] = None
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    x_url: Optional[str] = None
    bluesky_url: Optional[str] = None
    paypal_url: Optional[str] = None
    patreon_url: Optional[str] = None
    buymeacoffee_url: Optional[str] = None

    @field_validator("subtitle")
    @classmethod
    def sanitize_subtitle(cls, value: Optional[str]) -> Optional[str]:
        return _sanitize_optional_profile_text(value)

    @field_validator("avatar_seed", "cover_seed")
    @classmethod
    def trim_seed(cls, value: Optional[str]) -> Optional[str]:
        return _trim_optional_string(value, 100, "Seed")

    @field_validator("location")
    @classmethod
    def trim_location(cls, value: Optional[str]) -> Optional[str]:
        return _trim_optional_string(value, 120, "Locația")

    @field_validator(
        "youtube_playlist_url",
        "facebook_url",
        "instagram_url",
        "tiktok_url",
        "x_url",
        "bluesky_url",
        "paypal_url",
        "patreon_url",
        "buymeacoffee_url",
    )
    @classmethod
    def trim_url(cls, value: Optional[str]) -> Optional[str]:
        return _trim_optional_string(value, 1000, "Linkul")


class DataPortabilityMedia(BaseModel):
    profile_photo_url: Optional[str] = None
    cover_photo_url: Optional[str] = None
    avatar_url: Optional[str] = None
    cover_url: Optional[str] = None


class DataPortabilityPostMetrics(BaseModel):
    view_count: int = Field(default=0, ge=0)
    likes_count: int = Field(default=0, ge=0)
    super_likes_count: int = Field(default=0, ge=0)


class DataPortabilityAudioLink(BaseModel):
    playback_url: Optional[str] = None
    download_url: Optional[str] = None
    source: Optional[str] = None
    content_type: Optional[str] = None
    duration_seconds: Optional[float] = None


class DataPortabilityPost(BaseModel):
    stable_id: str = Field(..., min_length=1, max_length=500)
    source_id: Optional[int] = Field(None, ge=1)
    title: str = Field(..., min_length=1, max_length=255)
    slug: Optional[str] = Field(None, max_length=300)
    content: str
    explanatory_note: Optional[str] = Field(None, max_length=300)
    category: Optional[PostCategory] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    public_url: Optional[str] = None
    metrics: DataPortabilityPostMetrics = Field(default_factory=DataPortabilityPostMetrics)
    audio: Optional[DataPortabilityAudioLink] = None

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return _trim_required_string(value, 255, "Titlul")

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: str) -> str:
        return _sanitize_required_rich_text(value)

    @field_validator("explanatory_note")
    @classmethod
    def trim_explanatory_note(cls, value: Optional[str]) -> Optional[str]:
        return _trim_optional_string(value, 300, "Nota explicativă")


class DataExportManifest(BaseModel):
    format: str = "calimara-user-export"
    version: int = 1
    export_id: str = Field(..., min_length=1, max_length=100)
    exported_at: datetime
    source_username: Optional[str] = None
    profile: DataPortabilityProfile = Field(default_factory=DataPortabilityProfile)
    media: DataPortabilityMedia = Field(default_factory=DataPortabilityMedia)
    posts: list[DataPortabilityPost] = Field(default_factory=list)


class DataImportCreatedPost(BaseModel):
    title: str
    slug: str
    source_stable_id: str


class DataImportReport(BaseModel):
    profile_updated: bool = False
    posts_created: int = 0
    posts_skipped: int = 0
    posts_failed: int = 0
    created_posts: list[DataImportCreatedPost] = Field(default_factory=list)
    skipped_posts: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    message: str
