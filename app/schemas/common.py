from typing import Literal, Optional

from .. import rich_text

TITLE_CHARACTER_LIMIT = 120
POETRY_CHARACTER_LIMIT = 10000
SHORT_STORY_CHARACTER_LIMIT = 50000
COMMENT_CHARACTER_LIMIT = 2500
PROFILE_DESCRIPTION_CHARACTER_LIMIT = 1000
FORUM_THREAD_CHARACTER_LIMIT = 8000
FORUM_REPLY_CHARACTER_LIMIT = 4000

PostCategory = Literal["poezie", "proza_scurta"]

POST_CONTENT_CHARACTER_LIMITS = {
    "poezie": POETRY_CHARACTER_LIMIT,
    "proza_scurta": SHORT_STORY_CHARACTER_LIMIT,
}


def _visible_text_length(value: Optional[str]) -> int:
    return len(rich_text.rich_text_to_plain_text(value))


def _validate_visible_text_limit(value: Optional[str], limit: int, label: str) -> None:
    if value and _visible_text_length(value) > limit:
        raise ValueError(f"{label} poate avea cel mult {limit} de caractere")


def _sanitize_required_rich_text(value: str) -> str:
    cleaned = rich_text.sanitize_rich_text(value)
    if not rich_text.rich_text_to_plain_text(cleaned):
        raise ValueError("Conținutul este obligatoriu")
    return cleaned


def _sanitize_draft_rich_text(value: str) -> str:
    return rich_text.sanitize_rich_text(value)


def _sanitize_optional_profile_text(value: Optional[str]) -> Optional[str]:
    cleaned = rich_text.sanitize_optional_rich_text(value)
    _validate_visible_text_limit(
        cleaned,
        PROFILE_DESCRIPTION_CHARACTER_LIMIT,
        "Descrierea",
    )
    return cleaned


def _trim_optional_string(value: Optional[str], limit: int, label: str) -> Optional[str]:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > limit:
        raise ValueError(f"{label} poate avea cel mult {limit} de caractere")
    return trimmed


def _validate_post_content_limit(category: PostCategory, content: str) -> None:
    limit = POST_CONTENT_CHARACTER_LIMITS[category]
    label = "Poezia" if category == "poezie" else "Proza scurtă"
    _validate_visible_text_limit(content, limit, label)


__all__ = [
    "TITLE_CHARACTER_LIMIT",
    "POETRY_CHARACTER_LIMIT",
    "SHORT_STORY_CHARACTER_LIMIT",
    "COMMENT_CHARACTER_LIMIT",
    "PROFILE_DESCRIPTION_CHARACTER_LIMIT",
    "FORUM_THREAD_CHARACTER_LIMIT",
    "FORUM_REPLY_CHARACTER_LIMIT",
    "PostCategory",
    "POST_CONTENT_CHARACTER_LIMITS",
    "_visible_text_length",
    "_validate_visible_text_limit",
    "_sanitize_required_rich_text",
    "_sanitize_draft_rich_text",
    "_sanitize_optional_profile_text",
    "_trim_optional_string",
    "_validate_post_content_limit",
]
