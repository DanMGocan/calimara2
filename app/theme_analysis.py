import os
import logging
import json
from typing import Optional, List
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Configuration — all values from .env
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
THEME_ANALYSIS_ENABLED = os.getenv("THEME_ANALYSIS_ENABLED", "True").lower() == "true"
THEME_ANALYSIS_MODEL = os.getenv("THEME_ANALYSIS_MODEL", "mistral-small-latest")

# Initialize Mistral client
client = None
if MISTRAL_API_KEY and THEME_ANALYSIS_ENABLED:
    try:
        from mistralai.client import Mistral
        client = Mistral(api_key=MISTRAL_API_KEY)
        logger.info(f"Mistral theme analysis configured: model={THEME_ANALYSIS_MODEL}")
    except Exception as e:
        logger.error(f"Failed to initialize Mistral client for theme analysis: {e}")
else:
    if not MISTRAL_API_KEY:
        logger.warning("Mistral API key not provided - theme analysis will be disabled")
    if not THEME_ANALYSIS_ENABLED:
        logger.warning("Theme analysis is disabled in configuration")


class ThemeAnalysisResult:
    def __init__(self, themes: List[str], feelings: List[str], success: bool, reason: str = ""):
        self.themes = themes
        self.feelings = feelings
        self.success = success
        self.reason = reason


# --- LLM Theme Extraction ---

THEME_EXTRACTION_PROMPT = """Ești un analist literar expert pentru Calimara, o platformă românească de microblogging pentru scriitori și poeți.

Analizează textul de mai jos și identifică:
1. **Teme** (1-5): subiectele sau motivele principale ale textului (ex: dragoste, natura, moarte, timp, copilarie, dor)
2. **Sentimente** (1-5): emoțiile sau stările sufletești transmise de text (ex: tristete, bucurie, nostalgie, melancolie, speranta)

Folosește cuvinte scurte în română, cu litere mici, fără diacritice.

{existing_terms_section}

Returnează DOAR un JSON valid:
{{
    "themes": ["tema1", "tema2"],
    "feelings": ["sentiment1", "sentiment2"]
}}
"""


def _build_existing_terms_section(existing_themes: List[str], existing_feelings: List[str]) -> str:
    """Build the prompt section with existing DB terms for consistency."""
    if not existing_themes and not existing_feelings:
        return ""

    parts = ["Pe platformă sunt deja folosite următoarele cuvinte. Preferă să le refolosești dacă se potrivesc, dar poți crea altele noi dacă niciun termen existent nu descrie bine textul."]
    if existing_themes:
        parts.append(f"Teme existente: {', '.join(existing_themes)}")
    if existing_feelings:
        parts.append(f"Sentimente existente: {', '.join(existing_feelings)}")
    return "\n".join(parts)


def extract_themes_from_text(text: str, existing_themes: List[str], existing_feelings: List[str]) -> dict:
    """
    Call Mistral Small to extract themes and feelings from text.
    Returns dict with 'themes' (list) and 'feelings' (list).
    """
    existing_terms_section = _build_existing_terms_section(existing_themes, existing_feelings)
    system_prompt = THEME_EXTRACTION_PROMPT.format(existing_terms_section=existing_terms_section)

    response = client.chat.complete(
        model=THEME_ANALYSIS_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    response_text = response.choices[0].message.content.strip()
    try:
        result = json.loads(response_text)
        themes = result.get("themes", [])
        feelings = result.get("feelings", [])

        # Validate: ensure lists of strings, max 5 each
        themes = [str(t).lower().strip() for t in themes if isinstance(t, str)][:5]
        feelings = [str(f).lower().strip() for f in feelings if isinstance(f, str)][:5]

        return {"themes": themes, "feelings": feelings}
    except json.JSONDecodeError:
        logger.error(f"Failed to parse theme extraction response: {response_text[:200]}")
        return {"themes": [], "feelings": []}


# --- Public API ---

def analyze_post_themes(title: str, content: str, db: Session) -> ThemeAnalysisResult:
    """
    Analyze a post's themes and feelings using Mistral AI.
    Fetches existing terms from DB for consistency.
    """
    if not THEME_ANALYSIS_ENABLED or not client:
        return ThemeAnalysisResult(
            themes=[], feelings=[], success=False,
            reason="Theme analysis is disabled"
        )

    try:
        from . import crud

        existing_themes = crud.get_distinct_themes(db)
        existing_feelings = crud.get_distinct_feelings(db)

        full_text = f"Titlu: {title}\n\nConținut: {content}"
        logger.info(f"Analyzing themes for post: {title[:30]}...")

        result = extract_themes_from_text(full_text, existing_themes, existing_feelings)

        logger.info(f"Theme analysis complete: themes={result['themes']}, feelings={result['feelings']}")

        return ThemeAnalysisResult(
            themes=result["themes"],
            feelings=result["feelings"],
            success=True
        )

    except Exception as e:
        logger.error(f"Theme analysis error: {e}")
        return ThemeAnalysisResult(
            themes=[], feelings=[], success=False,
            reason=f"Theme analysis error: {str(e)}"
        )
