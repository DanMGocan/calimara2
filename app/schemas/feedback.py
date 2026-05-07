from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


SiteFeedbackKind = Literal["feedback", "bug"]
SiteFeedbackStatus = Literal["open", "closed"]


class SiteFeedbackCreate(BaseModel):
    kind: SiteFeedbackKind
    message: str = Field(..., min_length=1, max_length=2000)
    page_url: Optional[str] = Field(None, max_length=1000)
    client_context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("message")
    @classmethod
    def trim_message(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Mesajul este obligatoriu.")
        return trimmed


class SiteFeedbackUpdate(BaseModel):
    status: SiteFeedbackStatus
    admin_note: Optional[str] = Field(None, max_length=2000)


class SiteFeedbackOut(BaseModel):
    id: int
    kind: SiteFeedbackKind
    user_id: Optional[int] = None
    username_snapshot: Optional[str] = None
    email_snapshot: Optional[str] = None
    message: str
    page_url: Optional[str] = None
    user_agent: Optional[str] = None
    client_context: dict[str, Any] = Field(default_factory=dict)
    status: SiteFeedbackStatus
    admin_note: Optional[str] = None
    resolved_by: Optional[int] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
