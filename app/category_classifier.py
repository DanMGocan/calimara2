import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
CATEGORY_CLASSIFIER_MODEL = os.getenv("CATEGORY_CLASSIFIER_MODEL", "mistral-small-latest")

client = None
if MISTRAL_API_KEY:
    try:
        from mistralai.client import Mistral
        client = Mistral(api_key=MISTRAL_API_KEY)
        logger.info(f"Mistral category classifier configured: model={CATEGORY_CLASSIFIER_MODEL}")
    except Exception as e:
        logger.error(f"Failed to initialize Mistral client for category classifier: {e}")

CLASSIFIER_PROMPT = """Ești un clasificator literar pentru Calimara, o platformă românească de microblogging pentru scriitori și poeți.

Clasifică textul de mai jos în una din cele două categorii:
- "poezie" — dacă textul este o poezie (versuri, rime, strofe, vers liber, haiku, sonet, etc.)
- "proza_scurta" — dacă textul este proză scurtă (povestire, eseu, jurnal, scrisoare, fragment narativ, etc.)

Analizează structura textului (versuri vs paragrafe), prezența rimelor, ritmul, și stilul general.

Returnează DOAR un JSON valid:
{"category": "poezie"}
sau
{"category": "proza_scurta"}
"""


def classify_post(title: str, content: str) -> str:
    """Classify a post as 'poezie' or 'proza_scurta' using Mistral AI.
    Returns the category key. Defaults to 'proza_scurta' on failure."""
    if not client:
        logger.warning("Mistral client not available, defaulting to proza_scurta")
        return "proza_scurta"

    try:
        full_text = f"Titlu: {title}\n\nConținut: {content}"
        response = client.chat.complete(
            model=CATEGORY_CLASSIFIER_MODEL,
            messages=[
                {"role": "system", "content": CLASSIFIER_PROMPT},
                {"role": "user", "content": full_text},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content.strip())
        category = result.get("category", "proza_scurta")

        if category not in ("poezie", "proza_scurta"):
            logger.warning(f"Unexpected category from AI: {category}, defaulting to proza_scurta")
            return "proza_scurta"

        logger.info(f"Post classified as: {category}")
        return category

    except Exception as e:
        logger.error(f"Category classification failed: {e}")
        return "proza_scurta"
