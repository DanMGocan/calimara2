import html
import re

import bleach


ALLOWED_RICH_TEXT_TAGS = [
    "p",
    "br",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "blockquote",
    "ol",
    "ul",
    "li",
]

SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style)\b[^>]*>.*?</\1>")
BR_RE = re.compile(r"(?i)<br\s*/?>")
BLOCK_END_RE = re.compile(r"(?i)</(p|div|blockquote|li|h[1-6])>")
HTML_RE = re.compile(r"<[a-zA-Z][^>]*>")
INVISIBLE_TEXT_RE = re.compile(r"[\u200B-\u200D\uFEFF]")
NBSP_ENTITY_RE = re.compile(r"(?i)&nbsp;")
SOFT_HYPHEN_ENTITY_RE = re.compile(r"(?i)&shy;")


def normalize_editor_artifacts(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).replace("\u00a0", " ").replace("\u00ad", "")
    text = NBSP_ENTITY_RE.sub(" ", text)
    return SOFT_HYPHEN_ENTITY_RE.sub("", text)


def strip_invisible_text(value: str) -> str:
    return INVISIBLE_TEXT_RE.sub("", value)


def rich_text_to_plain_text(value: str | None) -> str:
    if not value:
        return ""

    raw = strip_invisible_text(normalize_editor_artifacts(SCRIPT_STYLE_RE.sub("", str(value))))
    raw = BR_RE.sub("\n", raw)
    raw = BLOCK_END_RE.sub("\n", raw)
    text = bleach.clean(raw, tags=[], strip=True)
    text = html.unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sanitize_rich_text(value: str | None) -> str:
    if not value:
        return ""

    raw = strip_invisible_text(normalize_editor_artifacts(SCRIPT_STYLE_RE.sub("", str(value)))).strip()
    if not rich_text_to_plain_text(raw):
        return ""

    if HTML_RE.search(raw):
        cleaned = bleach.clean(
            raw,
            tags=ALLOWED_RICH_TEXT_TAGS,
            attributes={},
            strip=True,
        )
        return cleaned.strip()

    return raw


def sanitize_optional_rich_text(value: str | None) -> str | None:
    cleaned = sanitize_rich_text(value)
    return cleaned or None
