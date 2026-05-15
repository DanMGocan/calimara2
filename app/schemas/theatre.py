from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .common import _sanitize_required_rich_text, _trim_optional_string, _validate_visible_text_limit


THEATRE_TITLE_LIMIT = 160
THEATRE_DESCRIPTION_LIMIT = 3000
THEATRE_CHARACTER_NAME_LIMIT = 120
THEATRE_CHARACTER_DESCRIPTION_LIMIT = 2500
THEATRE_ENTRY_LIMIT = 8000
THEATRE_NOTE_LIMIT = 1000

TheatrePlayStatus = Literal["setup", "active", "completed"]
TheatreCharacterStatus = Literal["pending", "approved", "rejected"]
TheatreMemberRole = Literal["creator", "actor"]
TheatreJoinDirection = Literal["application", "invitation"]
TheatreJoinStatus = Literal["pending", "approved", "rejected"]
TheatreSceneStatus = Literal["active", "ended"]
TheatreEntryType = Literal["scene_opening", "line", "stage_direction", "scene_end"]
TheatreModerationStatus = Literal["pending", "approved", "flagged", "rejected"]
TheatreAssignmentStatus = Literal["liber", "utilizator_invitat", "personaj_atribuit"]


class TheatreUserRef(BaseModel):
    id: int
    username: str
    avatar_seed: Optional[str] = None
    is_premium: bool = False
    premium_tier: str = "free"


class TheatreCharacterInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=THEATRE_CHARACTER_NAME_LIMIT)
    description: str = Field(..., min_length=1, max_length=THEATRE_CHARACTER_DESCRIPTION_LIMIT)
    assigned_username: Optional[str] = Field(None, max_length=255)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("description")
    @classmethod
    def trim_description(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Descrierea personajului este obligatorie")
        return trimmed

    @field_validator("assigned_username")
    @classmethod
    def trim_username(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value and value.strip() else None


class TheatrePlayCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=THEATRE_TITLE_LIMIT)
    description: Optional[str] = Field(None, max_length=THEATRE_DESCRIPTION_LIMIT)
    characters: List[TheatreCharacterInput] = Field(default_factory=list, max_length=40)

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        return value.strip()

    @field_validator("description")
    @classmethod
    def trim_description(cls, value: Optional[str]) -> Optional[str]:
        return _trim_optional_string(value, THEATRE_DESCRIPTION_LIMIT, "Descrierea")


class TheatrePlayUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=THEATRE_TITLE_LIMIT)
    description: Optional[str] = Field(None, max_length=THEATRE_DESCRIPTION_LIMIT)
    status: Optional[TheatrePlayStatus] = None

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value and value.strip() else None

    @field_validator("description")
    @classmethod
    def trim_description(cls, value: Optional[str]) -> Optional[str]:
        return _trim_optional_string(value, THEATRE_DESCRIPTION_LIMIT, "Descrierea")


class TheatreCharacterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=THEATRE_CHARACTER_NAME_LIMIT)
    description: str = Field(..., min_length=1, max_length=THEATRE_CHARACTER_DESCRIPTION_LIMIT)

    @field_validator("name", "description")
    @classmethod
    def trim_required(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Câmp obligatoriu")
        return trimmed


class TheatreCharacterReview(BaseModel):
    action: Literal["approve", "reject"]


class TheatreCharacterAssign(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)

    @field_validator("username")
    @classmethod
    def trim_username(cls, value: str) -> str:
        return value.strip()


class TheatreJoinApply(BaseModel):
    character_id: Optional[int] = Field(None, ge=1)
    proposed_character: Optional[TheatreCharacterCreate] = None
    note: Optional[str] = Field(None, max_length=THEATRE_NOTE_LIMIT)

    @field_validator("note")
    @classmethod
    def trim_note(cls, value: Optional[str]) -> Optional[str]:
        return _trim_optional_string(value, THEATRE_NOTE_LIMIT, "Mesajul")


class TheatreInvite(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    character_id: Optional[int] = Field(None, ge=1)
    note: Optional[str] = Field(None, max_length=THEATRE_NOTE_LIMIT)

    @field_validator("username")
    @classmethod
    def trim_username(cls, value: str) -> str:
        return value.strip()

    @field_validator("note")
    @classmethod
    def trim_note(cls, value: Optional[str]) -> Optional[str]:
        return _trim_optional_string(value, THEATRE_NOTE_LIMIT, "Mesajul")


class TheatreJoinRespond(BaseModel):
    action: Literal["approve", "reject"]


class TheatreSceneCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=THEATRE_TITLE_LIMIT)
    content: str
    first_character_id: int = Field(..., ge=1)

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        return value.strip()

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: str) -> str:
        cleaned = _sanitize_required_rich_text(value)
        _validate_visible_text_limit(cleaned, THEATRE_ENTRY_LIMIT, "Indicația de început")
        return cleaned


class TheatreReplyCreate(BaseModel):
    content: str
    next_character_id: int = Field(..., ge=1)

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: str) -> str:
        cleaned = _sanitize_required_rich_text(value)
        _validate_visible_text_limit(cleaned, THEATRE_ENTRY_LIMIT, "Replica")
        return cleaned


class TheatreStageDirectionCreate(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: str) -> str:
        cleaned = _sanitize_required_rich_text(value)
        _validate_visible_text_limit(cleaned, THEATRE_ENTRY_LIMIT, "Indicația scenică")
        return cleaned


class TheatreTurnOverride(BaseModel):
    character_id: int = Field(..., ge=1)
    note: Optional[str] = Field(None, max_length=THEATRE_ENTRY_LIMIT)

    @field_validator("note")
    @classmethod
    def sanitize_note(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = _sanitize_required_rich_text(value)
        _validate_visible_text_limit(cleaned, THEATRE_ENTRY_LIMIT, "Indicația scenică")
        return cleaned


class TheatreSceneEnd(BaseModel):
    content: Optional[str] = Field(None, max_length=THEATRE_ENTRY_LIMIT)

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = _sanitize_required_rich_text(value)
        _validate_visible_text_limit(cleaned, THEATRE_ENTRY_LIMIT, "Încheierea scenei")
        return cleaned


class TheatreMemberOut(BaseModel):
    id: int
    user_id: int
    user: Optional[TheatreUserRef] = None
    role: TheatreMemberRole
    joined_at: datetime


class TheatreCharacterOut(BaseModel):
    id: int
    play_id: int
    name: str
    description: str
    status: TheatreCharacterStatus
    proposed_by: Optional[int] = None
    proposer: Optional[TheatreUserRef] = None
    assigned_user_id: Optional[int] = None
    assigned_user: Optional[TheatreUserRef] = None
    assignment_status: Optional[TheatreAssignmentStatus] = None
    pending_invitation_user: Optional[TheatreUserRef] = None
    created_at: datetime
    approved_at: Optional[datetime] = None


class TheatreJoinRequestOut(BaseModel):
    id: int
    play_id: int
    user: TheatreUserRef
    direction: TheatreJoinDirection
    status: TheatreJoinStatus
    initiator_id: int
    character: Optional[TheatreCharacterOut] = None
    note: Optional[str] = None
    created_at: datetime
    responded_at: Optional[datetime] = None


class TheatreEntryOut(BaseModel):
    id: int
    play_id: int
    scene_id: int
    author: Optional[TheatreUserRef] = None
    character: Optional[TheatreCharacterOut] = None
    next_character: Optional[TheatreCharacterOut] = None
    entry_type: TheatreEntryType
    content: str
    position: int
    moderation_status: TheatreModerationStatus
    moderation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TheatreSceneOut(BaseModel):
    id: int
    play_id: int
    scene_number: int
    title: str
    status: TheatreSceneStatus
    created_at: datetime
    ended_at: Optional[datetime] = None
    entries: List[TheatreEntryOut] = Field(default_factory=list)


class TheatrePlaySummary(BaseModel):
    id: int
    creator_id: int
    title: str
    slug: str
    description: Optional[str] = None
    status: TheatrePlayStatus
    creator: Optional[TheatreUserRef] = None
    character_count: int = 0
    actor_count: int = 0
    scene_count: int = 0
    current_scene_id: Optional[int] = None
    current_character_id: Optional[int] = None
    current_actor_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class TheatrePlayDetail(TheatrePlaySummary):
    members: List[TheatreMemberOut] = Field(default_factory=list)
    characters: List[TheatreCharacterOut] = Field(default_factory=list)
    scenes: List[TheatreSceneOut] = Field(default_factory=list)
    current_character: Optional[TheatreCharacterOut] = None
    my_role: Optional[TheatreMemberRole] = None
    my_character_ids: List[int] = Field(default_factory=list)
    my_pending_request_status: Optional[TheatreJoinDirection] = None
    pending_request_count: Optional[int] = None
    pending_character_count: Optional[int] = None


class TheatrePendingItem(BaseModel):
    request: TheatreJoinRequestOut
    play: TheatrePlaySummary
    direction: TheatreJoinDirection


TheatrePlayDetail.model_rebuild()
TheatreSceneOut.model_rebuild()
TheatreEntryOut.model_rebuild()
