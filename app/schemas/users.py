from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator, model_validator

from .common import *

class UserBase(BaseModel):
    username: str
    email: EmailStr
    google_id: Optional[str] = None
    facebook_id: Optional[str] = None
    subtitle: Optional[str] = None # User motto
    avatar_seed: Optional[str] = None # DiceBear avatar seed
    cover_seed: Optional[str] = None # DiceBear cover seed
    location: Optional[str] = None
    youtube_playlist_url: Optional[str] = None
    
    # Social media links
    facebook_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    instagram_url: Optional[str] = None
    x_url: Optional[str] = None
    bluesky_url: Optional[str] = None
    
    # Donation/support links
    patreon_url: Optional[str] = None
    paypal_url: Optional[str] = None
    buymeacoffee_url: Optional[str] = None


class UserSetup(BaseModel):
    username: str
    subtitle: Optional[str] = None
    avatar_seed: str
    cover_seed: Optional[str] = None

    @field_validator("subtitle")
    @classmethod
    def sanitize_subtitle(cls, value: Optional[str]) -> Optional[str]:
        return _sanitize_optional_profile_text(value)

    @field_validator("cover_seed")
    @classmethod
    def sanitize_cover_seed(cls, value: Optional[str]) -> Optional[str]:
        return _trim_optional_string(value, 100, "Coperta")


class UserProfileUpdate(BaseModel):
    subtitle: Optional[str] = None
    avatar_seed: Optional[str] = None
    cover_seed: Optional[str] = None
    location: Optional[str] = None

    @field_validator("subtitle")
    @classmethod
    def sanitize_subtitle(cls, value: Optional[str]) -> Optional[str]:
        return _sanitize_optional_profile_text(value)

    @field_validator("location")
    @classmethod
    def sanitize_location(cls, value: Optional[str]) -> Optional[str]:
        return _trim_optional_string(value, 120, "Locația")

    @field_validator("cover_seed")
    @classmethod
    def sanitize_cover_seed(cls, value: Optional[str]) -> Optional[str]:
        return _trim_optional_string(value, 100, "Coperta")


class GoogleUserInfo(BaseModel):
    google_id: str
    email: str
    name: str
    picture: Optional[str] = None
    email_verified: bool = True


class FacebookUserInfo(BaseModel):
    facebook_id: str
    email: str
    name: str
    picture: Optional[str] = None
    email_verified: bool = True


class PasswordRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=10, max_length=128)


class PasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class AuthCodeVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=4, max_length=32)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=4, max_length=32)
    password: str = Field(..., min_length=10, max_length=128)


class UserInDB(UserBase):
    id: int
    is_premium: bool = False
    has_audio_access: bool = False
    has_author_audio_access: bool = False
    premium_tier: str = "free"
    premium_period_start: Optional[datetime] = None
    premium_until: Optional[datetime] = None
    gologani_balance: int = 0
    seconds_listened: int = 0
    last_login_at: Optional[datetime] = None
    email_comment_notifications: bool = True
    email_mention_notifications: bool = True
    email_analytics_digest: bool = True
    email_admin_announcements: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmailPreferences(BaseModel):
    email_comment_notifications: bool = True
    email_mention_notifications: bool = True
    email_analytics_digest: bool = True
    email_admin_announcements: bool = True

class SocialLinksUpdate(BaseModel):
    facebook_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    instagram_url: Optional[str] = None
    x_url: Optional[str] = None
    bluesky_url: Optional[str] = None
    patreon_url: Optional[str] = None
    paypal_url: Optional[str] = None
    buymeacoffee_url: Optional[str] = None
    youtube_playlist_url: Optional[str] = None

    @field_validator(
        "facebook_url",
        "tiktok_url",
        "instagram_url",
        "x_url",
        "bluesky_url",
        "patreon_url",
        "paypal_url",
        "buymeacoffee_url",
        "youtube_playlist_url",
    )
    @classmethod
    def sanitize_url(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        limit = 500 if info.field_name == "youtube_playlist_url" else 300
        return _trim_optional_string(value, limit, "Linkul")



class UserProfileSettingsUpdate(BaseModel):
    subtitle: Optional[str] = None
    avatar_seed: Optional[str] = None
    cover_seed: Optional[str] = None
    location: Optional[str] = None
    youtube_playlist_url: Optional[str] = None
    facebook_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    instagram_url: Optional[str] = None
    x_url: Optional[str] = None
    bluesky_url: Optional[str] = None
    patreon_url: Optional[str] = None
    paypal_url: Optional[str] = None
    buymeacoffee_url: Optional[str] = None

    @field_validator("subtitle")
    @classmethod
    def sanitize_subtitle(cls, value: Optional[str]) -> Optional[str]:
        return _sanitize_optional_profile_text(value)

    @field_validator("avatar_seed")
    @classmethod
    def sanitize_avatar_seed(cls, value: Optional[str]) -> Optional[str]:
        return _trim_optional_string(value, 100, "Avatarul")

    @field_validator("cover_seed")
    @classmethod
    def sanitize_cover_seed(cls, value: Optional[str]) -> Optional[str]:
        return _trim_optional_string(value, 100, "Coperta")

    @field_validator("location")
    @classmethod
    def sanitize_location(cls, value: Optional[str]) -> Optional[str]:
        return _trim_optional_string(value, 120, "Locația")

    @field_validator(
        "facebook_url",
        "tiktok_url",
        "instagram_url",
        "x_url",
        "bluesky_url",
        "patreon_url",
        "paypal_url",
        "buymeacoffee_url",
        "youtube_playlist_url",
    )
    @classmethod
    def sanitize_url(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        limit = 500 if info.field_name == "youtube_playlist_url" else 300
        return _trim_optional_string(value, limit, "Linkul")


class BestFriendsUpdate(BaseModel):
    friends: List[str] = Field(default_factory=list, max_length=3, description="List of promoted author usernames (max 3)")


class FeaturedPostsUpdate(BaseModel):
    post_ids: List[Optional[int]] = Field(default_factory=list, max_length=2, description="List of own post IDs (max 2)")


class UserPromotionsUpdate(BaseModel):
    own_post_ids: List[int] = Field(default_factory=list, max_length=2)
    author_ids: List[int] = Field(default_factory=list, max_length=3)
    other_post_ids: List[int] = Field(default_factory=list, max_length=3)
