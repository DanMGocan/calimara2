import os
import logging
import json
import re
from typing import Dict, Tuple, Optional
from enum import Enum
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from . import email_service
from .mistral_context import validate_chat_context, validate_text_context
from .rich_text import rich_text_to_plain_text

load_dotenv()

logger = logging.getLogger(__name__)

# Configuration — all values from .env
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MODERATION_ENABLED = os.getenv("MODERATION_ENABLED", "True").lower() == "true"
MODERATION_CLASSIFIER_MODEL = os.getenv("MODERATION_CLASSIFIER_MODEL", "mistral-moderation-2603")
MODERATION_REVIEW_MODEL = os.getenv("MODERATION_REVIEW_MODEL", "mistral-small-latest")
MODERATION_REVIEW_MAX_TOKENS = int(os.getenv("MODERATION_REVIEW_MAX_TOKENS", "600"))
MODERATION_THRESHOLD = float(os.getenv("MODERATION_THRESHOLD", "0.2"))
ROMANIAN_CONTEXT_AWARE = os.getenv("ROMANIAN_CONTEXT_AWARE", "True").lower() == "true"

# Initialize Mistral client
client = None
if MISTRAL_API_KEY and MODERATION_ENABLED:
    try:
        from mistralai.client import Mistral
        client = Mistral(api_key=MISTRAL_API_KEY)
        logger.info(
            f"Mistral moderation configured: classifier={MODERATION_CLASSIFIER_MODEL}, "
            f"review={MODERATION_REVIEW_MODEL}, threshold={MODERATION_THRESHOLD}"
        )
    except Exception as e:
        logger.error(f"Failed to initialize Mistral client: {e}")
else:
    if not MISTRAL_API_KEY:
        logger.warning("Mistral API key not provided - moderation will be disabled")
    if not MODERATION_ENABLED:
        logger.warning("Moderation is disabled in configuration")


class ModerationStatus(str, Enum):
    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"
    FLAGGED = "flagged"


class ModerationResult:
    def __init__(self, status: ModerationStatus, toxicity_score: float, reason: str, details: Optional[Dict] = None):
        self.status = status
        self.toxicity_score = toxicity_score
        self.reason = reason
        self.details = details or {}


# --- Romanian pattern matching (additional signal for Pass 2) ---

ROMANIAN_PROFANITY_PATTERNS = [
    "pula", "pulă", "muie", "futut", "cacat", "căcat", "nenorocit", "jegos",
    "curvă", "curve", "pizda", "pizdă", "dracu", "mortii", "morții", "naiba",
    "dumnezeu", "ma-ta", "mă-ta", "ma-tii", "mă-tii", "idiot", "prost",
    "tâmpit", "tampit", "retardat", "debil", "cretin"
]

ROMANIAN_HATE_SPEECH_PATTERNS = [
    "cioară", "jidan", "evreu de căcat", "țigan împuțit", "tigan imputit"
]


def _count_pattern_matches(text: str, patterns: list[str]) -> int:
    text_lower = text.lower()
    count = 0
    for pattern in patterns:
        escaped = re.escape(pattern.lower())
        count += len(re.findall(rf"(?<!\w){escaped}(?!\w)", text_lower))
    return count


def contains_romanian_profanity(text: str) -> Tuple[bool, float]:
    profanity_count = _count_pattern_matches(text, ROMANIAN_PROFANITY_PATTERNS)
    if profanity_count == 0:
        return False, 0.0
    total_words = max(1, len(text.split()))
    severity = min(1.0, profanity_count / total_words * 10)
    return True, severity


def contains_romanian_hate_speech(text: str) -> Tuple[bool, float]:
    hate_count = _count_pattern_matches(text, ROMANIAN_HATE_SPEECH_PATTERNS)
    if hate_count == 0:
        return False, 0.0
    severity = min(1.0, hate_count * 0.8)
    return True, severity


def romanian_content_signals(text: str) -> Dict:
    has_profanity, profanity_score = contains_romanian_profanity(text)
    has_hate, hate_score = contains_romanian_hate_speech(text)
    return {
        "profanity_detected": has_profanity,
        "profanity_score": profanity_score,
        "hate_speech_detected": has_hate,
        "hate_speech_score": hate_score,
    }


# --- Pass 1: Mistral Moderation classifier ---

MODERATION_CATEGORIES = [
    "sexual", "hate_and_discrimination", "violence_and_threats", "dangerous",
    "criminal", "dangerous_and_criminal_content", "selfharm", "health",
    "financial", "law", "pii", "jailbreaking",
]


def _field_value(source, key: str, default):
    if isinstance(source, dict):
        return source.get(key, default)
    if hasattr(source, "model_dump"):
        dumped = source.model_dump()
        if isinstance(dumped, dict):
            return dumped.get(key, default)
    return getattr(source, key, default)


def _score_value(source, key: str) -> float:
    try:
        return float(_field_value(source, key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _flag_value(source, key: str) -> bool:
    return bool(_field_value(source, key, False))


def classify_content(text: str) -> Dict:
    """
    Pass 1: Run text through Mistral Moderation 2 classifier.
    Returns dict with 'category_scores', 'categories', and 'flagged' keys.
    """
    validate_text_context(
        model=MODERATION_CLASSIFIER_MODEL,
        texts=[text],
        max_output_tokens=0,
        purpose="Moderare automată",
    )
    response = client.classifiers.moderate(
        model=MODERATION_CLASSIFIER_MODEL,
        inputs=[text]
    )
    result = response.results[0]

    # Extract scores and boolean flags
    scores = {}
    flags = {}
    for cat in MODERATION_CATEGORIES:
        scores[cat] = _score_value(result.category_scores, cat)
        flags[cat] = _flag_value(result.categories, cat)

    dangerous_aggregate = max(
        scores.get("dangerous", 0.0),
        scores.get("criminal", 0.0),
        scores.get("dangerous_and_criminal_content", 0.0),
    )
    scores["dangerous_and_criminal_content"] = dangerous_aggregate
    flags["dangerous_and_criminal_content"] = (
        flags.get("dangerous", False)
        or flags.get("criminal", False)
        or flags.get("dangerous_and_criminal_content", False)
    )

    flagged_cats = {
        k: scores[k]
        for k, provider_flagged in flags.items()
        if provider_flagged or scores.get(k, 0.0) >= MODERATION_THRESHOLD
    }
    max_score = max(scores.values()) if scores else 0.0

    return {
        "category_scores": scores,
        "categories": flags,
        "flagged_categories": flagged_cats,
        "max_score": max_score,
        "is_clean": len(flagged_cats) == 0,
    }


# --- Pass 2: Mistral Small 4 LLM review ---

ROMANIAN_REVIEW_PROMPT = """Ești un moderator de conținut pentru Călimara, o platformă românească de microblogging pentru scriitori și poeți.

Un sistem automat de moderare a semnalizat următorul text. Sarcina ta este să decizi dacă textul este SIGUR pentru publicare sau dacă trebuie RESPINS.

Ia în considerare:
- Contextul LITERAR și artistic: poezia, proza și teatrul pot conține teme întunecate, violență simbolică sau limbaj puternic ca expresie artistică
- Nuanțele culturale românești: sarcasmul, umorul negru, expresiile idiomatice
- Diferența între exprimarea artistică și atacurile personale reale
- Diferența între ficțiune/literatură și incitare reală la violență sau ură

Returnează DOAR un JSON valid:
{
    "safe": true/false,
    "reason": "Explicație scurtă în română despre decizia ta"
}

Dacă textul este expresie artistică legitimă (chiar dacă are teme întunecate), marchează-l ca "safe": true.
Marchează "safe": false DOAR dacă textul conține:
- Atacuri personale directe sau hărțuire reală
- Incitare explicită la violență sau ură
- Conținut sexual explicit non-artistic
- Informații personale expuse (PII)
- Conținut periculos/criminal real (nu ficțional)
"""


def review_content_with_llm(text: str, flagged_categories: Dict, romanian_signals: Dict) -> Dict:
    """
    Pass 2: Mistral Small 4 reviews flagged content with literary context.
    Returns dict with 'safe' (bool) and 'reason' (str).
    """
    user_message = (
        f"Categorii semnalizate automat: {json.dumps(flagged_categories, ensure_ascii=False)}\n"
        f"Semnale românești: {json.dumps(romanian_signals, ensure_ascii=False)}\n\n"
        f"Text de evaluat:\n{text}"
    )

    messages = [
        {"role": "system", "content": ROMANIAN_REVIEW_PROMPT},
        {"role": "user", "content": user_message},
    ]
    validate_chat_context(
        model=MODERATION_REVIEW_MODEL,
        messages=messages,
        max_output_tokens=MODERATION_REVIEW_MAX_TOKENS,
        purpose="Revizie moderare Mistral Small",
    )
    response = client.chat.complete(
        model=MODERATION_REVIEW_MODEL,
        messages=messages,
        max_tokens=MODERATION_REVIEW_MAX_TOKENS,
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    response_text = response.choices[0].message.content.strip()
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse LLM review response: {response_text[:200]}")
        return {"safe": False, "reason": "Eroare la parsarea răspunsului LLM - trimis la moderare manuală"}


# --- Core two-pass moderation pipeline ---

def _moderate_text(text: str) -> ModerationResult:
    """
    Two-pass moderation pipeline:
      Pass 1 (Mistral Moderation 2): fast classifier
        → clean → APPROVED
        → flagged → Pass 2
      Pass 2 (Mistral Small 4): LLM review with literary context
        → safe → APPROVED
        → unsafe → FLAGGED (manual moderation queue)
    """
    if not MODERATION_ENABLED:
        return ModerationResult(
            status=ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason="Moderation disabled"
        )

    if not client:
        logger.warning("Mistral client not configured - sending content to moderation queue")
        return ModerationResult(
            status=ModerationStatus.FLAGGED,
            toxicity_score=0.0,
            reason="Mistral API not configured - sent to manual review"
        )

    try:
        # --- Pass 1: Classifier ---
        logger.info(f"Pass 1 (classifier): analyzing text ({len(text)} chars)")
        classification = classify_content(text)
        romanian_signals = romanian_content_signals(text)
        local_score = max(
            romanian_signals["profanity_score"],
            romanian_signals["hate_speech_score"],
        )
        toxicity_score = max(classification["max_score"], local_score)

        if romanian_signals["profanity_detected"] or romanian_signals["hate_speech_detected"]:
            logger.info("Romanian content signals detected; sending to manual review")
            return ModerationResult(
                status=ModerationStatus.FLAGGED,
                toxicity_score=toxicity_score,
                reason="Romanian profanity or direct insult detected - sent to manual review",
                details={
                    **classification["category_scores"],
                    "pass1_flagged": classification["flagged_categories"],
                    "romanian_signals": romanian_signals,
                }
            )

        if classification["is_clean"]:
            logger.info(f"Pass 1: CLEAN (max_score={classification['max_score']:.3f})")
            return ModerationResult(
                status=ModerationStatus.APPROVED,
                toxicity_score=classification["max_score"],
                reason="Pass 1 (classifier): content is clean",
                details={
                    **classification["category_scores"],
                    "romanian_signals": romanian_signals,
                }
            )

        flagged = classification["flagged_categories"]
        logger.info(f"Pass 1: FLAGGED categories={list(flagged.keys())}, proceeding to Pass 2")

        # --- Pass 2: LLM review ---
        logger.info("Pass 2 (LLM review): evaluating with literary context")
        llm_verdict = review_content_with_llm(text, flagged, romanian_signals)

        if llm_verdict.get("safe", False):
            logger.info(f"Pass 2: SAFE — {llm_verdict.get('reason', '')}")
            return ModerationResult(
                status=ModerationStatus.APPROVED,
                toxicity_score=toxicity_score,
                reason=f"Pass 2 (LLM review): {llm_verdict.get('reason', 'approved by LLM')}",
                details={
                    **classification["category_scores"],
                    "pass1_flagged": flagged,
                    "pass2_verdict": llm_verdict,
                    "romanian_signals": romanian_signals,
                }
            )

        # Both passes reject → manual moderation queue
        logger.info(f"Pass 2: UNSAFE — {llm_verdict.get('reason', '')}")
        return ModerationResult(
            status=ModerationStatus.FLAGGED,
            toxicity_score=toxicity_score,
            reason=f"Flagged for manual review: {llm_verdict.get('reason', 'rejected by both passes')}",
            details={
                **classification["category_scores"],
                "pass1_flagged": flagged,
                "pass2_verdict": llm_verdict,
                "romanian_signals": romanian_signals,
            }
        )

    except Exception as e:
        logger.error(f"Moderation pipeline error: {e}")
        return ModerationResult(
            status=ModerationStatus.FLAGGED,
            toxicity_score=0.0,
            reason=f"Moderation error - sent to manual review: {str(e)}"
        )


# --- Public API (unchanged interface) ---

def moderate_comment(content: str) -> ModerationResult:
    plain_content = rich_text_to_plain_text(content)
    logger.info(f"Moderating comment ({len(plain_content)} chars)")
    return _moderate_text(plain_content)


def moderate_post(title: str, content: str) -> ModerationResult:
    logger.info(f"Moderating post: {title[:30]}...")
    full_text = f"Titlu: {title}\n\nConținut: {rich_text_to_plain_text(content)}"
    return _moderate_text(full_text)


def moderate_forum_thread(title: str, content: str) -> ModerationResult:
    logger.info(f"Moderating forum thread: {title[:30]}...")
    full_text = f"Titlu discuție: {title}\n\nConținut: {rich_text_to_plain_text(content)}"
    return _moderate_text(full_text)


def moderate_forum_reply(content: str) -> ModerationResult:
    plain_content = rich_text_to_plain_text(content)
    logger.info(f"Moderating forum reply ({len(plain_content)} chars)")
    return _moderate_text(plain_content)


def moderate_theatre_entry(entry_type: str, content: str, character_name: Optional[str] = None) -> ModerationResult:
    plain_content = rich_text_to_plain_text(content)
    label = {
        "scene_opening": "Deschidere de scenă",
        "line": "Replică de teatru",
        "stage_direction": "Indicație scenică",
        "scene_end": "Încheiere de scenă",
    }.get(entry_type, "Text de teatru")
    character_part = f"\nPersonaj: {character_name}" if character_name else ""
    full_text = f"{label}{character_part}\n\nConținut:\n{plain_content}"
    logger.info(f"Moderating theatre entry ({len(plain_content)} chars)")
    return _moderate_text(full_text)


def moderate_stafeta_segment(content: str, title: Optional[str] = None) -> ModerationResult:
    plain_content = rich_text_to_plain_text(content)
    title_part = f"Titlu ștafetă: {title}\n\n" if title else ""
    full_text = f"{title_part}Contribuție Ștafeta:\n{plain_content}"
    logger.info(f"Moderating stafeta segment ({len(plain_content)} chars)")
    return _moderate_text(full_text)


def should_auto_approve(moderation_result: ModerationResult) -> bool:
    return moderation_result.status == ModerationStatus.APPROVED


def should_auto_reject(moderation_result: ModerationResult) -> bool:
    return moderation_result.status == ModerationStatus.REJECTED


def needs_manual_review(moderation_result: ModerationResult) -> bool:
    return moderation_result.status in [ModerationStatus.FLAGGED, ModerationStatus.PENDING]


# --- Logging ---

def log_moderation_decision(
    db: Session,
    content_type: str,
    content_id: int,
    user_id: Optional[int],
    moderation_result: ModerationResult
) -> None:
    try:
        from .models import ModerationLog

        details = moderation_result.details or {}

        log_entry = ModerationLog(
            content_type=content_type,
            content_id=content_id,
            user_id=user_id,
            ai_decision=moderation_result.status.value,
            toxicity_score=moderation_result.toxicity_score,
            harassment_score=details.get("hate_and_discrimination", 0.0),
            hate_speech_score=details.get("hate_and_discrimination", 0.0),
            sexually_explicit_score=details.get("sexual", 0.0),
            dangerous_content_score=details.get("dangerous_and_criminal_content", 0.0),
            romanian_profanity_score=details.get("romanian_signals", {}).get("profanity_score", 0.0)
                if isinstance(details.get("romanian_signals"), dict) else 0.0,
            ai_reason=moderation_result.reason,
            ai_details=json.loads(json.dumps(details, ensure_ascii=False, default=str)) if details else None,
            human_decision="pending" if moderation_result.status == ModerationStatus.FLAGGED else None
        )

        db.add(log_entry)
        logger.info(f"Logged moderation decision for {content_type} {content_id}: {moderation_result.status.value}")

    except Exception as e:
        logger.error(f"Failed to log moderation decision: {e}")
        try:
            db.rollback()
        except Exception as rollback_error:
            logger.error(f"Database rollback failed: {rollback_error}")


def _queue_moderation_service_alert(
    db: Session,
    *,
    content_type: str,
    content_id: int,
    user_id: Optional[int],
    result: ModerationResult,
) -> None:
    reason = result.reason or ""
    if not (
        reason.startswith("Moderation error")
        or reason.startswith("Mistral API not configured")
    ):
        return
    email_service.queue_system_alert_email(
        db,
        service="AI moderation",
        summary="Moderarea automată a fost degradată și a trimis conținutul la revizie manuală.",
        error_message=reason,
        context={
            "content_type": content_type,
            "content_id": content_id,
            "user_id": user_id,
        },
    )


def moderate_comment_with_logging(content: str, comment_id: int, user_id: Optional[int], db: Session) -> ModerationResult:
    result = moderate_comment(content)
    _queue_moderation_service_alert(db, content_type="comment", content_id=comment_id, user_id=user_id, result=result)
    try:
        log_moderation_decision(db, "comment", comment_id, user_id, result)
    except Exception as e:
        logger.error(f"Failed to log moderation for comment {comment_id}: {e}")
    return result


def moderate_post_with_logging(title: str, content: str, post_id: int, user_id: int, db: Session) -> ModerationResult:
    result = moderate_post(title, content)
    _queue_moderation_service_alert(db, content_type="post", content_id=post_id, user_id=user_id, result=result)
    try:
        log_moderation_decision(db, "post", post_id, user_id, result)
    except Exception as e:
        logger.error(f"Failed to log moderation for post {post_id}: {e}")
    return result


def moderate_forum_thread_with_logging(title: str, content: str, thread_id: int, user_id: int, db: Session) -> ModerationResult:
    result = moderate_forum_thread(title, content)
    _queue_moderation_service_alert(db, content_type="forum_thread", content_id=thread_id, user_id=user_id, result=result)
    try:
        log_moderation_decision(db, "forum_thread", thread_id, user_id, result)
    except Exception as e:
        logger.error(f"Failed to log moderation for forum thread {thread_id}: {e}")
    return result


def moderate_forum_reply_with_logging(content: str, reply_id: int, user_id: int, db: Session) -> ModerationResult:
    result = moderate_forum_reply(content)
    _queue_moderation_service_alert(db, content_type="forum_reply", content_id=reply_id, user_id=user_id, result=result)
    try:
        log_moderation_decision(db, "forum_reply", reply_id, user_id, result)
    except Exception as e:
        logger.error(f"Failed to log moderation for forum reply {reply_id}: {e}")
    return result


def moderate_theatre_entry_with_logging(
    entry_type: str,
    content: str,
    entry_id: int,
    user_id: int,
    db: Session,
    character_name: Optional[str] = None,
) -> ModerationResult:
    result = moderate_theatre_entry(entry_type, content, character_name)
    _queue_moderation_service_alert(db, content_type="theatre_entry", content_id=entry_id, user_id=user_id, result=result)
    try:
        log_moderation_decision(db, "theatre_entry", entry_id, user_id, result)
    except Exception as e:
        logger.error(f"Failed to log moderation for theatre entry {entry_id}: {e}")
    return result


def moderate_stafeta_segment_with_logging(
    content: str,
    segment_id: int,
    user_id: int,
    db: Session,
    title: Optional[str] = None,
) -> ModerationResult:
    result = moderate_stafeta_segment(content, title)
    _queue_moderation_service_alert(db, content_type="stafeta_segment", content_id=segment_id, user_id=user_id, result=result)
    try:
        log_moderation_decision(db, "stafeta_segment", segment_id, user_id, result)
    except Exception as e:
        logger.error(f"Failed to log moderation for stafeta segment {segment_id}: {e}")
    return result
