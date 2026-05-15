import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv

from . import rich_text

load_dotenv()

logger = logging.getLogger(__name__)

DIACRITICS_ENABLED = os.getenv("DIACRITICS_ENABLED", "True").lower() == "true"
DIACRITICS_MODEL = os.getenv("DIACRITICS_MODEL", "mistral-small-latest")
DIACRITICS_MAX_TOKENS = int(os.getenv("DIACRITICS_MAX_TOKENS", "4000"))
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

client = None
if DIACRITICS_ENABLED and MISTRAL_API_KEY:
    try:
        from mistralai.client import Mistral

        client = Mistral(api_key=MISTRAL_API_KEY)
        logger.info("AI diacritics configured: model=%s", DIACRITICS_MODEL)
    except Exception as exc:
        logger.error("Failed to initialize Mistral client for AI diacritics: %s", exc)
elif not MISTRAL_API_KEY:
    logger.warning("AI diacritics: MISTRAL_API_KEY missing")


DIACRITICS_PROMPT = """Ești un editor român specializat în restaurarea diacriticelor.

Primești texte românești scrise fără diacritice sau cu diacritice incomplete. Sarcina ta este să adaugi contextual doar diacriticele corecte: ă, â, î, ș, ț și variantele majuscule.

Reguli stricte:
- Nu rescrie textul, nu schimba stilul, sensul, ordinea propozițiilor sau cuvintele.
- Nu corecta gramatica, punctuația sau ortografia dacă nu ține strict de diacritice.
- Păstrează exact paragrafele, rândurile goale, spațiile relevante, semnele de punctuație și majusculele.
- Dacă textul conține HTML, păstrează structura și tagurile HTML existente; modifică doar textul din interiorul tagurilor.
- Dacă un cuvânt poate primi mai multe forme, alege forma potrivită contextului.
- Păstrează numele proprii, username-urile, URL-urile, emailurile, codul și citatele străine dacă diacriticele nu sunt evidente.

Returnează DOAR JSON valid:
{
  "title": "titlul cu diacritice sau null",
  "content": "textul cu diacritice"
}
"""

THEATRE_DIACRITICS_PROMPT = """Ești un editor român specializat în restaurarea diacriticelor.

Primești datele unei piese de teatru colaborativ: titlu, descrierea piesei și descrierile personajelor. Sarcina ta este să adaugi contextual doar diacriticele corecte: ă, â, î, ș, ț și variantele majuscule.

Reguli stricte:
- Nu rescrie textul, nu schimba stilul, sensul, ordinea propozițiilor sau cuvintele.
- Nu corecta gramatica, punctuația sau ortografia dacă nu ține strict de diacritice.
- Păstrează exact paragrafele, rândurile goale, spațiile relevante, semnele de punctuație și majusculele.
- Păstrează numele proprii, username-urile, URL-urile, emailurile, codul și citatele străine dacă diacriticele nu sunt evidente.
- Nu modifica indexurile personajelor.

Returnează DOAR JSON valid:
{
  "title": "titlul cu diacritice sau null",
  "description": "descrierea piesei cu diacritice sau null",
  "characters": [
    { "index": 0, "description": "descrierea personajului cu diacritice" }
  ]
}
"""


def _load_json_response(text: str) -> dict:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Răspunsul AI pentru diacritice nu a fost JSON valid.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Răspunsul AI pentru diacritice a avut format invalid.")
    return parsed


def add_diacritics(*, title: Optional[str], content: str, kind: str) -> dict:
    if not DIACRITICS_ENABLED:
        raise RuntimeError("Conversia automată la diacritice este dezactivată.")
    if not client:
        raise RuntimeError("Serviciul AI pentru diacritice nu este configurat.")

    original_title = title if title is not None else None
    original_content = rich_text.sanitize_rich_text(content)
    user_message = {
        "kind": kind,
        "title": original_title,
        "content": original_content,
    }

    response = client.chat.complete(
        model=DIACRITICS_MODEL,
        max_tokens=DIACRITICS_MAX_TOKENS,
        messages=[
            {"role": "system", "content": DIACRITICS_PROMPT},
            {"role": "user", "content": json.dumps(user_message, ensure_ascii=False)},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    parsed = _load_json_response((response.choices[0].message.content or "").strip())
    converted_title = parsed.get("title", original_title)
    converted_content = parsed.get("content")

    if original_title is None:
        converted_title = None
    elif not isinstance(converted_title, str):
        converted_title = original_title

    if isinstance(converted_content, str):
        converted_content = rich_text.sanitize_rich_text(converted_content)

    if not isinstance(converted_content, str) or not rich_text.rich_text_to_plain_text(converted_content):
        raise RuntimeError("Serviciul AI nu a returnat un text valid.")

    return {
        "title": converted_title,
        "content": converted_content,
        "changed": converted_title != original_title or converted_content != original_content,
    }


def add_theatre_play_diacritics(
    *,
    title: Optional[str],
    description: Optional[str],
    characters: list[dict],
) -> dict:
    if not DIACRITICS_ENABLED:
        raise RuntimeError("Conversia automată la diacritice este dezactivată.")
    if not client:
        raise RuntimeError("Serviciul AI pentru diacritice nu este configurat.")

    original_title = title if title is not None else None
    original_description = description if description is not None else None
    original_characters = [
        {
            "index": int(item.get("index", index)),
            "description": str(item.get("description") or ""),
        }
        for index, item in enumerate(characters or [])
    ]
    user_message = {
        "kind": "theatre_play",
        "title": original_title,
        "description": original_description,
        "characters": original_characters,
    }

    response = client.chat.complete(
        model=DIACRITICS_MODEL,
        max_tokens=DIACRITICS_MAX_TOKENS,
        messages=[
            {"role": "system", "content": THEATRE_DIACRITICS_PROMPT},
            {"role": "user", "content": json.dumps(user_message, ensure_ascii=False)},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    parsed = _load_json_response((response.choices[0].message.content or "").strip())
    converted_title = parsed.get("title", original_title)
    converted_description = parsed.get("description", original_description)
    converted_items = parsed.get("characters", [])

    if original_title is None:
        converted_title = None
    elif not isinstance(converted_title, str):
        converted_title = original_title

    if original_description is None:
        converted_description = None
    elif not isinstance(converted_description, str):
        converted_description = original_description

    converted_by_index = {}
    if isinstance(converted_items, list):
        for item in converted_items:
            if not isinstance(item, dict):
                continue
            try:
                index = int(item.get("index"))
            except (TypeError, ValueError):
                continue
            description_value = item.get("description")
            if isinstance(description_value, str):
                converted_by_index[index] = description_value

    converted_characters = []
    for item in original_characters:
        converted_description_value = converted_by_index.get(item["index"], item["description"])
        converted_characters.append({
            "index": item["index"],
            "description": converted_description_value,
        })

    changed = (
        converted_title != original_title
        or converted_description != original_description
        or converted_characters != original_characters
    )
    return {
        "title": converted_title,
        "description": converted_description,
        "characters": converted_characters,
        "changed": changed,
    }
