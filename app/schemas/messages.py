from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator, model_validator

from .common import *
from .users import UserBase


def _clean_message_content(value: str) -> str:
    content = value.strip()
    if not content:
        raise ValueError("Mesajul nu poate fi gol")
    return content


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        return _clean_message_content(value)


class MessageToUser(BaseModel):
    recipient_username: str
    content: str = Field(..., min_length=1, max_length=2000)

    @model_validator(mode="before")
    @classmethod
    def accept_username_alias(cls, data):
        if isinstance(data, dict) and "recipient_username" not in data and "username" in data:
            return {**data, "recipient_username": data["username"]}
        return data

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        return _clean_message_content(value)


class MessageBase(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    content: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Message(MessageBase):
    sender: Optional[UserBase] = None


class ConversationBase(BaseModel):
    id: int
    user1_id: int
    user2_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Conversation(ConversationBase):
    user1: Optional[UserBase] = None
    user2: Optional[UserBase] = None
    messages: List[Message] = Field(default_factory=list)
    

class ConversationSummary(BaseModel):
    id: int
    other_user: UserBase
    latest_message: Optional[MessageBase] = None
    unread_count: int = 0
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
# ===================================
# MODERATION & ADMIN SCHEMAS
# ===================================
