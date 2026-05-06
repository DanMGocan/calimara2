from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator, model_validator

from .common import *

DiacriticsKind = Literal["post", "forum_thread", "forum_reply", "comment"]

class DiacriticsRequest(BaseModel):
    kind: DiacriticsKind
    title: Optional[str] = Field(None, max_length=TITLE_CHARACTER_LIMIT)
    content: str = Field(..., min_length=1)
    category: Optional[PostCategory] = None

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: str) -> str:
        return _sanitize_required_rich_text(value)

    @model_validator(mode="after")
    def validate_request_limits(self):
        if self.kind == "post":
            if self.category is None:
                raise ValueError("Categoria este obligatorie pentru texte")
            _validate_post_content_limit(self.category, self.content)
        elif self.kind == "comment":
            _validate_visible_text_limit(self.content, COMMENT_CHARACTER_LIMIT, "Comentariul")
        elif self.kind == "forum_thread":
            _validate_visible_text_limit(self.content, FORUM_THREAD_CHARACTER_LIMIT, "Mesajul")
        elif self.kind == "forum_reply":
            _validate_visible_text_limit(self.content, FORUM_REPLY_CHARACTER_LIMIT, "Răspunsul")
        return self



class DiacriticsResponse(BaseModel):
    title: Optional[str] = None
    content: str
    changed: bool = False


