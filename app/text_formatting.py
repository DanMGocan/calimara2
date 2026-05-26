import json
import logging
import os

from dotenv import load_dotenv

from . import rich_text
from .mistral_context import validate_chat_context
from .schemas.common import POST_CONTENT_CHARACTER_LIMITS, PostCategory

load_dotenv()

logger = logging.getLogger(__name__)

AI_FORMATTING_ENABLED = os.getenv("AI_FORMATTING_ENABLED", "True").lower() == "true"
AI_FORMATTING_MODEL = os.getenv("AI_FORMATTING_MODEL", "mistral-small-latest")
AI_FORMATTING_MAX_TOKENS = int(os.getenv("AI_FORMATTING_MAX_TOKENS", "6000"))
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

client = None
if AI_FORMATTING_ENABLED and MISTRAL_API_KEY:
    try:
        from mistralai.client import Mistral

        client = Mistral(api_key=MISTRAL_API_KEY)
        logger.info("AI post formatter configured: model=%s", AI_FORMATTING_MODEL)
    except Exception as exc:
        logger.error("Failed to initialize Mistral client for AI post formatting: %s", exc)
elif not MISTRAL_API_KEY:
    logger.warning("AI post formatting: MISTRAL_API_KEY missing")


POST_FORMATTING_PROMPT = """Ești un editor literar român. Primești text copiat în editorul Călimara, uneori cu rânduri rupte aiurea, pauze ciudate, paragrafe sparte de PDF/Word/Google Docs sau HTML murdar.

Sarcina ta:
- Înțelege dacă textul este poezie sau proză scurtă.
- Curăță DOAR formatarea: paragrafe, strofe, versuri, spații și rânduri.
- Nu rescrie stilul autorului, nu corecta artistic, nu adăuga idei și nu șterge conținut.
- Poți corecta doar artefacte evidente de copiere: rânduri rupte în mijlocul frazei, spații multiple, paragrafe goale în exces, caractere invizibile.
- Pentru poezie: păstrează versurile pe rânduri separate, folosește <br> între versuri și <p> separat pentru fiecare strofă.
- Pentru proză scurtă: unește rândurile rupte accidental în același paragraf și folosește <p> pentru paragrafe reale.
- Păstrează bold/italic/underline/listă/citat doar când par intenționate.
- Returnează HTML curat acceptat de platformă: numai <p>, <br>, <strong>, <em>, <b>, <i>, <u>, <blockquote>, <ol>, <ul>, <li>.
- Nu folosi Markdown, titluri HTML, span, div, style, class, font, linkuri sau imagini.

Returnează DOAR JSON valid:
{
  "category": "poezie" sau "proza_scurta",
  "content": "HTML curat"
}
"""


def _load_json_response(text: str) -> dict:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Răspunsul AI pentru formatare nu a fost JSON valid.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Răspunsul AI pentru formatare a avut format invalid.")
    return parsed


def _validate_post_limit(category: str, content: str) -> None:
    limit = POST_CONTENT_CHARACTER_LIMITS.get(category)
    if limit is None:
        raise RuntimeError("Serviciul AI a returnat o categorie invalidă.")
    if len(rich_text.rich_text_to_plain_text(content)) > limit:
        raise RuntimeError("Serviciul AI a returnat un text prea lung pentru categoria detectată.")


def _messages_for_post_formatting(*, content: str, category: PostCategory) -> list[dict]:
    original_content = rich_text.sanitize_rich_text(content)
    user_message = {
        "category_hint": category,
        "content": original_content,
    }
    return [
        {"role": "system", "content": POST_FORMATTING_PROMPT},
        {"role": "user", "content": json.dumps(user_message, ensure_ascii=False)},
    ]


def validate_post_formatting_context(*, content: str, category: PostCategory) -> None:
    validate_chat_context(
        model=AI_FORMATTING_MODEL,
        messages=_messages_for_post_formatting(content=content, category=category),
        max_output_tokens=AI_FORMATTING_MAX_TOKENS,
        purpose="Formatare text Mistral",
    )


def format_post_content(*, content: str, category: PostCategory) -> dict:
    if not AI_FORMATTING_ENABLED:
        raise RuntimeError("Curățarea formatării cu AI este dezactivată.")
    if not client:
        raise RuntimeError("Serviciul AI pentru formatare nu este configurat.")

    original_content = rich_text.sanitize_rich_text(content)
    messages = _messages_for_post_formatting(content=content, category=category)
    validate_post_formatting_context(content=content, category=category)

    try:
        response = client.chat.complete(
            model=AI_FORMATTING_MODEL,
            max_tokens=AI_FORMATTING_MAX_TOKENS,
            messages=messages,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.warning("AI post formatting request failed: %s", exc)
        raise RuntimeError("Serviciul AI pentru formatare este temporar indisponibil. Încearcă din nou.") from exc

    parsed = _load_json_response((response.choices[0].message.content or "").strip())
    detected_category = parsed.get("category", category)
    if detected_category not in POST_CONTENT_CHARACTER_LIMITS:
        detected_category = category

    formatted_content = parsed.get("content")
    if isinstance(formatted_content, str):
        formatted_content = rich_text.sanitize_rich_text(formatted_content)

    if not isinstance(formatted_content, str) or not rich_text.rich_text_to_plain_text(formatted_content):
        raise RuntimeError("Serviciul AI nu a returnat un text formatat valid.")

    _validate_post_limit(detected_category, formatted_content)

    return {
        "category": detected_category,
        "content": formatted_content,
        "changed": formatted_content != original_content or detected_category != category,
    }
