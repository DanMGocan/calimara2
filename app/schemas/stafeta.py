from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import PostCategory, _sanitize_required_rich_text, _trim_optional_string, _validate_visible_text_limit


STAFETA_TITLE_LIMIT = 160
STAFETA_NOTE_LIMIT = 1000
STAFETA_INITIAL_LIMIT = 10000
STAFETA_MAX_CONTRIBUTION_LIMIT = 10000

StafetaWorkStatus = Literal["active", "published", "cancelled"]
StafetaAssignmentStatus = Literal["pending", "active", "refused", "completed", "expired", "cancelled"]
StafetaAssignmentSource = Literal["creator", "specific", "random", "previous", "timeout", "return"]
StafetaModerationStatus = Literal["pending", "approved", "flagged", "rejected"]
StafetaTargetMode = Literal["random", "creator", "previous", "specific"]
StafetaCreateTargetMode = Literal["random", "specific"]
StafetaAssignmentAction = Literal["accept", "refuse"]
StafetaListFilter = Literal["all", "mine", "turn", "created", "published"]


class StafetaUserRef(BaseModel):
    id: int
    username: str
    avatar_seed: Optional[str] = None
    is_premium: bool = False
    premium_tier: str = "free"


class StafetaParticipationUpdate(BaseModel):
    participates: bool = True


class StafetaCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=STAFETA_TITLE_LIMIT)
    category: PostCategory = "poezie"
    initial_content: str
    deadline_days: Literal[1, 3, 7] = 1
    max_characters: int = Field(400, ge=1, le=STAFETA_MAX_CONTRIBUTION_LIMIT)
    first_target_mode: StafetaCreateTargetMode = "random"
    assigned_username: Optional[str] = Field(None, max_length=255)

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        return value.strip()

    @field_validator("initial_content")
    @classmethod
    def sanitize_initial_content(cls, value: str) -> str:
        cleaned = _sanitize_required_rich_text(value)
        _validate_visible_text_limit(cleaned, STAFETA_INITIAL_LIMIT, "Textul inițial")
        return cleaned

    @field_validator("assigned_username")
    @classmethod
    def trim_assigned_username(cls, value: Optional[str]) -> Optional[str]:
        return _trim_optional_string(value, 255, "Utilizatorul")

    @model_validator(mode="after")
    def validate_target(self):
        if self.first_target_mode == "specific" and not self.assigned_username:
            raise ValueError("Alege utilizatorul pentru prima trimitere.")
        return self


class StafetaSend(BaseModel):
    content: Optional[str] = None
    target_mode: StafetaTargetMode = "random"
    target_user_id: Optional[int] = Field(None, ge=1)

    @field_validator("content")
    @classmethod
    def sanitize_optional_content(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _sanitize_required_rich_text(value)

    @model_validator(mode="after")
    def validate_target(self):
        if self.target_mode in {"previous", "specific"} and not self.target_user_id:
            raise ValueError("Alege destinatarul.")
        return self


class StafetaAssignSpecific(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)

    @field_validator("username")
    @classmethod
    def trim_username(cls, value: str) -> str:
        return value.strip()


class StafetaAssignmentRespond(BaseModel):
    action: StafetaAssignmentAction


class StafetaParticipantOut(BaseModel):
    user: StafetaUserRef
    first_joined_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None


class StafetaAssignmentOut(BaseModel):
    id: int
    work_id: int
    user: Optional[StafetaUserRef] = None
    assigned_by: Optional[StafetaUserRef] = None
    source: StafetaAssignmentSource
    status: StafetaAssignmentStatus
    due_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StafetaSegmentOut(BaseModel):
    id: int
    work_id: int
    assignment_id: Optional[int] = None
    author: Optional[StafetaUserRef] = None
    content: str
    position: int
    next_target_mode: StafetaTargetMode
    next_target_user: Optional[StafetaUserRef] = None
    moderation_status: StafetaModerationStatus
    moderation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StafetaWorkSummary(BaseModel):
    id: int
    creator_id: int
    title: str
    slug: str
    category: PostCategory
    status: StafetaWorkStatus
    deadline_days: int
    max_characters: int
    creator: Optional[StafetaUserRef] = None
    current_holder: Optional[StafetaUserRef] = None
    current_assignment: Optional[StafetaAssignmentOut] = None
    approved_segment_count: int = 0
    participant_count: int = 0
    published_post_id: Optional[int] = None
    published_post_slug: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None


class StafetaWorkDetail(StafetaWorkSummary):
    segments: List[StafetaSegmentOut] = Field(default_factory=list)
    assignments: List[StafetaAssignmentOut] = Field(default_factory=list)
    previous_participants: List[StafetaParticipantOut] = Field(default_factory=list)
    my_role: Optional[Literal["creator", "holder", "participant", "invited"]] = None
    can_write: bool = False
    can_respond: bool = False
    participates: bool = False


class StafetaWorkList(BaseModel):
    works: List[StafetaWorkSummary] = Field(default_factory=list)
    participates: bool = False
