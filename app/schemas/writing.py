from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator, model_validator

from .common import *

DiacriticsKind = Literal["post", "forum_thread", "forum_reply", "comment", "theatre_play", "profile_description", "private_message"]

THEATRE_TITLE_LIMIT = 160
THEATRE_DESCRIPTION_LIMIT = 3000
THEATRE_CHARACTER_DESCRIPTION_LIMIT = 2500


class DiacriticsTheatreCharacter(BaseModel):
    index: int = Field(..., ge=0)
    description: str = Field(..., min_length=1, max_length=THEATRE_CHARACTER_DESCRIPTION_LIMIT)

    @field_validator("description", mode="before")
    @classmethod
    def trim_description(cls, value: str) -> str:
        return _trim_required_string(value, THEATRE_CHARACTER_DESCRIPTION_LIMIT, "Descrierea personajului")


class DiacriticsTheatreCharacterResponse(BaseModel):
    index: int
    description: str


class DiacriticsQuota(BaseModel):
    premium_tier: str
    limit: int
    used: int
    remaining: int
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    can_request: bool
    service_available: bool = True
    service_unavailable_reason: Optional[str] = None
    service_retry_after_seconds: Optional[int] = None


class DiacriticsRequest(BaseModel):
    kind: DiacriticsKind
    title: Optional[str] = Field(None, max_length=THEATRE_TITLE_LIMIT)
    content: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = Field(None, max_length=THEATRE_DESCRIPTION_LIMIT)
    characters: List[DiacriticsTheatreCharacter] = Field(default_factory=list, max_length=40)
    category: Optional[PostCategory] = None

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value: Optional[str]) -> Optional[str]:
        return _trim_optional_string(value, THEATRE_TITLE_LIMIT, "Titlul")

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: Optional[str]) -> Optional[str]:
        return _sanitize_required_rich_text(value) if value is not None else None

    @field_validator("description", mode="before")
    @classmethod
    def trim_description(cls, value: Optional[str]) -> Optional[str]:
        return _trim_optional_string(value, THEATRE_DESCRIPTION_LIMIT, "Descrierea")

    @model_validator(mode="after")
    def validate_request_limits(self):
        if self.kind == "post":
            if not self.content:
                raise ValueError("Textul este obligatoriu")
            if self.category is None:
                raise ValueError("Categoria este obligatorie pentru texte")
            _validate_post_content_limit(self.category, self.content)
        elif self.kind == "comment":
            if not self.content:
                raise ValueError("Comentariul este obligatoriu")
            _validate_visible_text_limit(self.content, COMMENT_CHARACTER_LIMIT, "Comentariul")
        elif self.kind == "forum_thread":
            if not self.content:
                raise ValueError("Mesajul este obligatoriu")
            _validate_visible_text_limit(self.content, FORUM_THREAD_CHARACTER_LIMIT, "Mesajul")
        elif self.kind == "forum_reply":
            if not self.content:
                raise ValueError("Răspunsul este obligatoriu")
            _validate_visible_text_limit(self.content, FORUM_REPLY_CHARACTER_LIMIT, "Răspunsul")
        elif self.kind == "theatre_play":
            if not (self.title or self.description or self.characters):
                raise ValueError("Piesa nu are text pentru diacritice")
        elif self.kind == "profile_description":
            if not self.content:
                raise ValueError("Descrierea este obligatorie")
            _validate_visible_text_limit(self.content, PROFILE_DESCRIPTION_CHARACTER_LIMIT, "Descrierea")
        elif self.kind == "private_message":
            if not self.content:
                raise ValueError("Mesajul este obligatoriu")
            _validate_visible_text_limit(self.content, PRIVATE_MESSAGE_CHARACTER_LIMIT, "Mesajul")
        return self



class DiacriticsResponse(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None
    characters: List[DiacriticsTheatreCharacterResponse] = Field(default_factory=list)
    changed: bool = False
    quota: Optional[DiacriticsQuota] = None


class PostFormatRequest(BaseModel):
    category: PostCategory
    content: str = Field(..., min_length=1)

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: str) -> str:
        return _sanitize_required_rich_text(value)

    @model_validator(mode="after")
    def validate_content_limit(self):
        _validate_post_content_limit(self.category, self.content)
        return self


class PostFormatResponse(BaseModel):
    category: PostCategory
    content: str
    changed: bool = False
