import os
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

AI_CRITIC_ENABLED = os.getenv("AI_CRITIC_ENABLED", "True").lower() == "true"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
FREE_USERS_MODEL = os.getenv("FREE_USERS_MODEL", "mistral-small-latest")
PREMIUM_USERS_MODEL = os.getenv("PREMIUM_USERS_MODEL", "claude-sonnet-4-6")
AI_CRITIC_MAX_TOKENS = int(os.getenv("AI_CRITIC_MAX_TOKENS", "400"))

CRITIQUE_MAX_CHARS = 1500

CRITIC_PROMPT = """Ești un critic literar român experimentat, cu ureche pentru poezia și proza scurtă contemporană. Cunoști tradiția literaturii române — de la Eminescu, Arghezi, Bacovia, Blaga și Nichita Stănescu până la vocile contemporane — și poți plasa un text în contextul ei atunci când e relevant.

Pe platforma Călimara primești texte de la scriitori amatori și semi-profesioniști (poezie sau proză scurtă) și ți se cere o opinie literară onestă, directă, în limba română. Rolul tău public pe platformă este „Robotul Călimara”, dar vocea ta este a unui critic care respectă autorul suficient cât să fie sincer.

Abordează textul astfel:
- Citește atent și identifică unul sau două elemente concrete care ies în evidență: o imagine, o metaforă, alegerea unui cuvânt, ritmul, cezura, construcția narativă, tonul, finalul.
- Numește ce funcționează și, dacă e cazul, ce slăbește textul. Nu evita observația critică, dar formuleaz-o cu respect — fără să umilești autorul.
- Dacă textul are ecouri dintr-un curent sau dintr-un autor anume, poți semnala asta pe scurt.
- Evită laudele generice („frumos text", „bravo", „emoționant") și evită rezumatul sau parafraza.
- Nu da note, nu da ierarhii, nu pretinde că ești om.

Forma răspunsului:
- 2–4 propoziții, concise, la persoana întâi.
- Fără introducere formală, fără ghilimele, fără prefixe de tip „Opinia mea:" sau „Robotul:".
- Returnează DOAR textul opiniei."""


mistral_client = None
anthropic_client = None

if AI_CRITIC_ENABLED:
    if MISTRAL_API_KEY:
        try:
            from mistralai.client import Mistral
            mistral_client = Mistral(api_key=MISTRAL_API_KEY)
            logger.info(f"AI critic configured (Mistral): model={FREE_USERS_MODEL}")
        except Exception as e:
            logger.error(f"Failed to initialize Mistral client for AI critic: {e}")
    else:
        logger.warning("AI critic: MISTRAL_API_KEY missing — free-tier critiques disabled")

    if ANTHROPIC_API_KEY:
        try:
            from anthropic import Anthropic
            anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
            logger.info(f"AI critic configured (Anthropic): model={PREMIUM_USERS_MODEL}")
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client for AI critic: {e}")
    else:
        logger.warning("AI critic: ANTHROPIC_API_KEY missing — premium critiques will fall back to free tier")
else:
    logger.info("AI critic disabled via AI_CRITIC_ENABLED")


def _build_user_message(title: str, content: str) -> str:
    return f"Titlu: {title}\n\nText:\n{content}"


def _critique_with_anthropic(title: str, content: str) -> Optional[str]:
    if not anthropic_client:
        return None
    response = anthropic_client.messages.create(
        model=PREMIUM_USERS_MODEL,
        max_tokens=AI_CRITIC_MAX_TOKENS,
        system=CRITIC_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(title, content)}],
    )
    parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    text = "".join(parts).strip()
    return text or None


def _critique_with_mistral(title: str, content: str) -> Optional[str]:
    if not mistral_client:
        return None
    response = mistral_client.chat.complete(
        model=FREE_USERS_MODEL,
        max_tokens=AI_CRITIC_MAX_TOKENS,
        messages=[
            {"role": "system", "content": CRITIC_PROMPT},
            {"role": "user", "content": _build_user_message(title, content)},
        ],
        temperature=0.7,
    )
    text = (response.choices[0].message.content or "").strip()
    return text or None


def generate_critique(title: str, content: str, is_premium: bool) -> Optional[str]:
    """Generate a short literary critique. Returns None on any failure."""
    if not AI_CRITIC_ENABLED:
        return None

    try:
        if is_premium and anthropic_client:
            critique = _critique_with_anthropic(title, content)
            provider = "anthropic"
        else:
            critique = _critique_with_mistral(title, content)
            provider = "mistral"

        if not critique:
            logger.warning(f"AI critic ({provider}) returned empty critique")
            return None

        critique = critique.strip().strip('"').strip()
        if len(critique) > CRITIQUE_MAX_CHARS:
            critique = critique[:CRITIQUE_MAX_CHARS].rsplit(" ", 1)[0] + "…"

        logger.info(f"AI critic ({provider}) generated {len(critique)} chars")
        return critique

    except Exception as e:
        logger.error(f"AI critic failed (premium={is_premium}): {e}")
        return None
