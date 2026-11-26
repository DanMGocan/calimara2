import difflib
import html
import logging
import os
import re
import time
from typing import Optional

import bleach
from sqlalchemy.orm import Session, joinedload

from . import audio_storage, crud, models, moderation

logger = logging.getLogger(__name__)


class TTSRequestError(Exception):
    pass


class TTSRequestForbidden(TTSRequestError):
    pass


class TTSRequestInvalid(TTSRequestError):
    pass


class TTSQuotaExceeded(TTSRequestError):
    def __init__(self, limit: int, used: int, requested: int):
        self.limit = limit
        self.used = used
        self.requested = requested
        self.remaining = max(0, limit - used)
        super().__init__("Audio character quota exceeded")


class TTSGenerationFailed(RuntimeError):
    pass


class AudioListenError(Exception):
    pass


class AudioListenForbidden(AudioListenError):
    pass


class AudioListenInvalid(AudioListenError):
    pass


class AudioListenNotFound(AudioListenError):
    pass


def audio_enabled() -> bool:
    return os.getenv("AUDIO_ENABLED", "False").lower() in ("true", "1", "yes")


def enqueue_tts_for_post(db: Session, post: models.Post) -> Optional[models.PostAudio]:
    return None


def process_pending_tts_jobs(db: Session, limit: int = 5) -> int:
    if not audio_enabled():
        return 0
    from . import ai_queue

    for audio in crud.get_pending_tts_audio_jobs(db, limit=limit):
        ai_queue.enqueue_tts_audio_job(db, audio)
    return ai_queue.process_ai_jobs(db, limit=limit)


def generate_tts_audio(
    db: Session,
    audio: models.PostAudio,
    *,
    mark_failed_on_error: bool = True,
) -> models.PostAudio:
    if audio.requester_user_id is None:
        return crud.update_post_audio(
            db,
            audio.id,
            status="cancelled",
            moderation_status="cancelled",
            moderation_reason="Automatic TTS generation was disabled",
            error_message=None,
        ) or audio
    audio = crud.update_post_audio(db, audio.id, status="processing", error_message=None) or audio
    post = (
        db.query(models.Post)
        .options(joinedload(models.Post.owner))
        .filter(models.Post.id == audio.post_id)
        .first()
    )
    if not post:
        crud.update_post_audio(db, audio.id, status="failed", error_message="Postarea nu a fost găsită")
        raise TTSGenerationFailed("Postarea nu a fost găsită")

    try:
        text = text_for_speech(post)
        if not text:
            raise RuntimeError("Postarea nu are text lizibil")
        content, content_type = synthesize_text(text, audio_id=audio.id, post_id=post.id)
        backend, key, byte_size = audio_storage.save_audio_bytes(
            post_id=post.id,
            source="tts",
            content=content,
            content_type=content_type,
        )
        return crud.update_post_audio(
            db,
            audio.id,
            status="ready",
            storage_backend=backend,
            storage_key=key,
            content_type=content_type,
            byte_size=byte_size,
            voice_name=os.getenv("GOOGLE_TTS_VOICE_NAME", "ro-RO-Chirp3-HD-Leda"),
            language_code=os.getenv("GOOGLE_TTS_LANGUAGE_CODE", "ro-RO"),
            moderation_status="approved",
            moderation_reason="Generated from approved post text",
            error_message=None,
        ) or audio
    except Exception as exc:
        logger.exception("TTS generation failed for post audio %s", audio.id)
        crud.update_post_audio(
            db,
            audio.id,
            status="failed" if mark_failed_on_error else "pending",
            error_message=str(exc),
        )
        raise TTSGenerationFailed(str(exc)) from exc


def text_for_speech(post: models.Post) -> str:
    body = strip_html(post.content)
    return f"{post.title}.\n\n{body}".strip()


def tts_character_count_for_post(post: models.Post) -> int:
    return len(text_for_speech(post))


def audio_quota_payload(db: Session, user: models.User) -> dict:
    limit = crud.audio_tts_quota_limit_for_user(user)
    period_start, period_end = crud.audio_tts_quota_period_for_user(user)
    used = 0
    if period_start and period_end:
        used = crud.get_user_audio_tts_character_usage(db, user.id, period_start, period_end)
    return {
        "premium_tier": user.premium_tier if user else "free",
        "limit": limit,
        "used": used,
        "remaining": max(0, limit - used),
        "period_start": period_start,
        "period_end": period_end,
        "can_request": bool(user and limit > 0 and period_start and period_end),
    }


def request_tts_for_posts(db: Session, user: models.User, post_ids: list[int]) -> dict:
    unique_ids = []
    seen = set()
    for post_id in post_ids:
        if post_id not in seen:
            unique_ids.append(post_id)
            seen.add(post_id)
    if not unique_ids:
        raise TTSRequestInvalid("Selectează cel puțin un text.")

    period_start, period_end = crud.audio_tts_quota_period_for_user(user)
    limit = crud.audio_tts_quota_limit_for_user(user)
    if not period_start or not period_end or limit <= 0:
        raise TTSRequestForbidden("Generarea audio nu are o cotă activă pentru contul tău.")

    posts = db.query(models.Post).filter(models.Post.id.in_(unique_ids)).all()
    posts_by_id = {post.id: post for post in posts}
    missing = [post_id for post_id in unique_ids if post_id not in posts_by_id]
    if missing:
        raise TTSRequestInvalid("Unul dintre texte nu a fost găsit.")

    queued = []
    skipped = []
    requested_characters = 0
    candidates = []

    for post_id in unique_ids:
        post = posts_by_id[post_id]
        if post.user_id != user.id:
            raise TTSRequestInvalid("Poți genera audio doar pentru textele tale.")
        if post.moderation_status != "approved":
            raise TTSRequestInvalid("Poți genera audio doar pentru textele aprobate.")

        crud.cancel_legacy_pending_tts_for_post(db, post.id)
        existing = crud.get_active_or_ready_tts_for_post(db, post.id)
        if existing and existing.status in {"pending", "processing", "ready"}:
            skipped.append(
                {
                    "post_id": post.id,
                    "title": post.title,
                    "status": existing.status,
                    "audio_id": existing.id,
                    "character_count": int(existing.tts_character_count or tts_character_count_for_post(post)),
                }
            )
            continue
        if existing and existing.status == "failed" and _tts_audio_is_retrying(db, existing):
            skipped.append(
                {
                    "post_id": post.id,
                    "title": post.title,
                    "status": "pending",
                    "audio_id": existing.id,
                    "character_count": int(existing.tts_character_count or tts_character_count_for_post(post)),
                }
            )
            continue

        character_count = tts_character_count_for_post(post)
        requested_characters += character_count
        candidates.append((post, character_count))

    used = crud.get_user_audio_tts_character_usage(db, user.id, period_start, period_end)
    if used + requested_characters > limit:
        raise TTSQuotaExceeded(limit=limit, used=used, requested=requested_characters)

    for post, character_count in candidates:
        audio = crud.create_tts_audio_request(
            db,
            post_id=post.id,
            requester_user_id=user.id,
            tts_character_count=character_count,
            quota_period_start=period_start,
            quota_period_end=period_end,
        )
        if audio_enabled():
            from . import ai_queue

            ai_queue.enqueue_tts_audio_job(db, audio)
        queued.append(
            {
                "post_id": post.id,
                "title": post.title,
                "status": audio.status,
                "audio_id": audio.id,
                "character_count": character_count,
            }
        )

    new_used = used + requested_characters
    return {
        "queued": queued,
        "skipped": skipped,
        "quota": {
            "premium_tier": user.premium_tier,
            "limit": limit,
            "used": new_used,
            "remaining": max(0, limit - new_used),
            "period_start": period_start,
            "period_end": period_end,
            "can_request": True,
        },
    }


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = bleach.clean(value, tags=[], strip=True)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def synthesize_text(
    text: str,
    *,
    audio_id: Optional[int] = None,
    post_id: Optional[int] = None,
) -> tuple[bytes, str]:
    from google.api_core import exceptions as google_exceptions
    from google.api_core.client_options import ClientOptions
    from google.cloud import texttospeech

    client_options = None
    region = os.getenv("GOOGLE_CLOUD_REGION", "global").strip().lower()
    if region and region != "global":
        client_options = ClientOptions(api_endpoint=f"{region}-texttospeech.googleapis.com")
    client = texttospeech.TextToSpeechClient(client_options=client_options)
    language_code = os.getenv("GOOGLE_TTS_LANGUAGE_CODE", "ro-RO")
    voice_name = os.getenv("GOOGLE_TTS_VOICE_NAME", "Kore")
    model_name = os.getenv("GOOGLE_TTS_MODEL_NAME", "").strip() or None
    style_prompt = os.getenv("GOOGLE_TTS_STYLE_PROMPT", "").strip() or None
    encoding_name = os.getenv("GOOGLE_TTS_AUDIO_ENCODING", "MP3").upper()
    encoding = getattr(texttospeech.AudioEncoding, encoding_name)

    voice_kwargs = {"language_code": language_code, "name": voice_name}
    if model_name:
        voice_kwargs["model_name"] = model_name
    voice = texttospeech.VoiceSelectionParams(**voice_kwargs)
    audio_config = texttospeech.AudioConfig(audio_encoding=encoding)
    chunks = split_text_for_tts(text)
    audio_parts: list[bytes] = []
    max_attempts = max(1, int(os.getenv("GOOGLE_TTS_MAX_ATTEMPTS", "3")))
    total_chunks = len(chunks)
    for index, chunk in enumerate(chunks, start=1):
        chunk_bytes = _byte_len(chunk)
        input_kwargs = {"text": chunk}
        if style_prompt:
            input_kwargs["prompt"] = style_prompt
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    "TTS chunk synthesis audio_id=%s post_id=%s chunk=%s/%s bytes=%s attempt=%s/%s",
                    audio_id,
                    post_id,
                    index,
                    total_chunks,
                    chunk_bytes,
                    attempt,
                    max_attempts,
                )
                response = client.synthesize_speech(
                    input=texttospeech.SynthesisInput(**input_kwargs),
                    voice=voice,
                    audio_config=audio_config,
                )
                break
            except (
                google_exceptions.ServiceUnavailable,
                google_exceptions.DeadlineExceeded,
                google_exceptions.ResourceExhausted,
            ) as exc:
                logger.warning(
                    "Retryable TTS chunk failure audio_id=%s post_id=%s chunk=%s/%s bytes=%s attempt=%s/%s error=%s",
                    audio_id,
                    post_id,
                    index,
                    total_chunks,
                    chunk_bytes,
                    attempt,
                    max_attempts,
                    exc,
                )
                if attempt >= max_attempts:
                    raise
                time.sleep(min(2 ** (attempt - 1), 8))
        audio_parts.append(response.audio_content)
    return b"".join(audio_parts), content_type_for_tts_encoding(encoding_name)


def split_text_for_tts(text: str) -> list[str]:
    max_bytes = int(os.getenv("GOOGLE_TTS_MAX_BYTES", os.getenv("GOOGLE_TTS_MAX_CHARS", "3200")))
    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidates = _split_long_paragraph(paragraph, max_bytes)
        for candidate in candidates:
            if not current:
                current = candidate
            elif _byte_len(f"{current}\n\n{candidate}") <= max_bytes:
                current = f"{current}\n\n{candidate}"
            else:
                chunks.append(current)
                current = candidate
    if current:
        chunks.append(current)
    return chunks or [_truncate_utf8(text, max_bytes)]


def _split_long_paragraph(paragraph: str, max_bytes: int) -> list[str]:
    if _byte_len(paragraph) <= max_bytes:
        return [paragraph]
    sentences = re.split(r"(?<=[.!?…])\s+", paragraph)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if _byte_len(sentence) > max_bytes:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_by_bytes(sentence, max_bytes))
        elif not current:
            current = sentence
        elif _byte_len(f"{current} {sentence}") <= max_bytes:
            current = f"{current} {sentence}"
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def _byte_len(value: str) -> int:
    return len(value.encode("utf-8"))


def _truncate_utf8(value: str, max_bytes: int) -> str:
    encoded = value.encode("utf-8")[:max_bytes]
    return encoded.decode("utf-8", errors="ignore").strip()


def _split_by_bytes(value: str, max_bytes: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for char in value:
        candidate = f"{current}{char}"
        if current and _byte_len(candidate) > max_bytes:
            chunks.append(current.strip())
            current = char
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks


def content_type_for_tts_encoding(encoding_name: str) -> str:
    return {
        "MP3": "audio/mpeg",
        "OGG_OPUS": "audio/ogg",
        "LINEAR16": "audio/wav",
        "MULAW": "audio/basic",
        "ALAW": "audio/basic",
    }.get(encoding_name, "application/octet-stream")


def create_author_recording(
    db: Session,
    post: models.Post,
    content: bytes,
    content_type: str,
    requester_user_id: int | None = None,
) -> models.PostAudio:
    backend, key, byte_size = audio_storage.save_audio_bytes(
        post_id=post.id,
        source="author",
        content=content,
        content_type=content_type,
    )
    audio = crud.create_post_audio(
        db,
        post_id=post.id,
        requester_user_id=requester_user_id,
        source="author",
        status="pending",
        storage_backend=backend,
        storage_key=key,
        content_type=content_type,
        byte_size=byte_size,
        moderation_status="pending",
        language_code=os.getenv("GOOGLE_STT_LANGUAGE_CODE", "ro-RO"),
    )
    crud.cancel_non_ready_author_audio_for_post(db, post.id, exclude_audio_id=audio.id)
    from . import ai_queue

    ai_queue.enqueue_author_audio_moderation_job(db, audio)
    return audio


def process_author_recording(db: Session, audio: models.PostAudio) -> models.PostAudio:
    audio = crud.update_post_audio(db, audio.id, status="processing", error_message=None) or audio
    post = (
        db.query(models.Post)
        .filter(models.Post.id == audio.post_id)
        .first()
    )
    if not post:
        return crud.update_post_audio(
            db,
            audio.id,
            status="failed",
            error_message="Postarea nu a fost găsită",
            moderation_status="failed",
            moderation_reason="Postarea nu a fost găsită",
        ) or audio
    try:
        content = audio_storage.load_audio_bytes(audio)
        transcript, confidence = transcribe_audio(content)
        result = moderation.moderate_comment(transcript, db)
        moderation.log_moderation_decision(db, "audio", audio.id, post.user_id, result)
        match_score = text_match_score(strip_html(post.content), transcript)

        if result.status != moderation.ModerationStatus.APPROVED:
            return crud.update_post_audio(
                db,
                audio.id,
                status="flagged",
                transcript=transcript,
                transcript_confidence=confidence,
                transcript_match_score=match_score,
                moderation_status=result.status.value,
                moderation_reason=result.reason,
            ) or audio

        min_match = float(os.getenv("AUDIO_TRANSCRIPT_MIN_MATCH", "0.25"))
        if match_score < min_match:
            return crud.update_post_audio(
                db,
                audio.id,
                status="flagged",
                transcript=transcript,
                transcript_confidence=confidence,
                transcript_match_score=match_score,
                moderation_status="flagged",
                moderation_reason="Transcript does not match the post text closely enough",
            ) or audio

        return crud.update_post_audio(
            db,
            audio.id,
            status="ready",
            transcript=transcript,
            transcript_confidence=confidence,
            transcript_match_score=match_score,
            moderation_status="approved",
            moderation_reason=result.reason,
        ) or audio
    except Exception as exc:
        logger.exception("Author audio moderation failed for post %s", post.id)
        return crud.update_post_audio(
            db,
            audio.id,
            status="failed",
            error_message=str(exc),
            moderation_status="failed",
            moderation_reason=str(exc),
        ) or audio


def transcribe_audio(content: bytes) -> tuple[str, Optional[float]]:
    from google.cloud.speech_v2 import SpeechClient
    from google.cloud.speech_v2.types import cloud_speech

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is required for Speech-to-Text")
    location = os.getenv("GOOGLE_STT_LOCATION", "eu")
    language_code = os.getenv("GOOGLE_STT_LANGUAGE_CODE", "ro-RO")
    model = os.getenv("GOOGLE_STT_MODEL", "chirp_3")
    profanity_filter = os.getenv("GOOGLE_STT_PROFANITY_FILTER", "True").lower() in ("true", "1", "yes")

    # Regional recognizers (e.g. "eu") must be called through their regional endpoint.
    client_options = None
    if location and location.strip().lower() != "global":
        from google.api_core.client_options import ClientOptions

        client_options = ClientOptions(api_endpoint=f"{location.strip().lower()}-speech.googleapis.com")
    client = SpeechClient(client_options=client_options)
    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        language_codes=[language_code],
        model=model,
        features=cloud_speech.RecognitionFeatures(
            enable_automatic_punctuation=True,
            profanity_filter=profanity_filter,
        ),
    )
    request = cloud_speech.RecognizeRequest(
        recognizer=f"projects/{project_id}/locations/{location}/recognizers/_",
        config=config,
        content=content,
    )
    response = client.recognize(request=request)
    transcripts: list[str] = []
    confidences: list[float] = []
    for result in response.results:
        if not result.alternatives:
            continue
        alternative = result.alternatives[0]
        if alternative.transcript:
            transcripts.append(alternative.transcript)
        if alternative.confidence:
            confidences.append(float(alternative.confidence))
    transcript = " ".join(transcripts).strip()
    if not transcript:
        raise RuntimeError("Speech-to-Text returned an empty transcript")
    confidence = sum(confidences) / len(confidences) if confidences else None
    return transcript, confidence


def text_match_score(expected: str, actual: str) -> float:
    expected_norm = _normalize_for_match(expected)
    actual_norm = _normalize_for_match(actual)
    if not expected_norm or not actual_norm:
        return 0.0
    return difflib.SequenceMatcher(None, expected_norm, actual_norm).ratio()


def _normalize_for_match(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-zăâîșţț0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def post_audio_status_payload(
    db: Session, post_id: int, current_user: Optional[models.User]
) -> dict:
    post = (
        db.query(models.Post)
        .options(joinedload(models.Post.owner))
        .filter(models.Post.id == post_id)
        .first()
    )
    if not post:
        return {
            "available": False,
            "can_listen": False,
            "requires_audio_tier": False,
            "author_audio_can_upload": False,
            "message": "Postarea nu a fost găsită",
        }
    author_audio = crud.get_latest_author_audio_for_post(db, post_id)
    author_can_upload = bool(
        current_user
        and post.user_id == current_user.id
        and current_user.has_author_audio_access
        and post.moderation_status == "approved"
    )
    if post.moderation_status != "approved":
        return {
            "available": False,
            "can_listen": False,
            "requires_audio_tier": False,
            "status": "post_pending",
            "title": post.title,
            "author_username": post.owner.username if post.owner else None,
            "author_audio_can_upload": False,
            "author_audio_status": author_audio.status if author_audio else "missing",
            "author_audio_message": author_audio_status_message(author_audio),
            "message": "Audio disponibil după aprobarea postării",
        }
    audio = crud.get_best_audio_for_post(db, post_id)
    latest = audio or crud.get_latest_audio_for_post(db, post_id)
    if latest and latest.source == "tts" and latest.requester_user_id is None and latest.status in {"pending", "processing"}:
        latest = None
    latest_status = _effective_tts_audio_status(db, latest)
    can_listen = audio is not None
    payload = {
        "available": audio is not None,
        "can_listen": can_listen,
        "requires_audio_tier": False,
        "status": latest_status if latest else "missing",
        "source": latest.source if latest else None,
        "audio_id": audio.id if audio else None,
        "playback_url": audio_storage.safe_playback_url(audio) if audio else None,
        "content_type": audio.content_type if audio else None,
        "title": post.title,
        "author_username": post.owner.username if post.owner else None,
        "author_audio_can_upload": author_can_upload,
        "author_audio_status": author_audio.status if author_audio else "missing",
        "author_audio_message": author_audio_status_message(author_audio),
    }
    if not audio:
        payload["message"] = audio_status_message(latest, retrying=_tts_audio_is_retrying(db, latest))
    return payload


def _tts_audio_is_retrying(db: Session, audio: Optional[models.PostAudio]) -> bool:
    if not audio or audio.source != "tts":
        return False
    if audio.status == "failed":
        return crud.has_active_tts_audio_job(db, audio.id)
    return bool(audio.status == "pending" and audio.error_message and crud.has_active_tts_audio_job(db, audio.id))


def _effective_tts_audio_status(db: Session, audio: Optional[models.PostAudio]) -> Optional[str]:
    if _tts_audio_is_retrying(db, audio):
        return "pending"
    return audio.status if audio else None


def audio_status_message(audio: Optional[models.PostAudio], *, retrying: bool = False) -> str:
    if not audio:
        return "Nu există încă fișier audio pentru acest text."
    if retrying:
        return "Generarea audio se reîncearcă."
    if audio.source == "author" and audio.status in ("pending", "processing"):
        return "Înregistrarea audio este în curs de transcriere și moderare."
    if audio.status == "pending":
        return "Fișierul audio este în coada de generare."
    if audio.status == "processing":
        return "Fișierul audio se generează."
    if audio.status == "flagged":
        return "Fișierul audio este în curs de revizuire."
    if audio.status == "rejected":
        return "Fișierul audio a fost respins."
    if audio.status == "failed":
        return "Generarea audio a eșuat."
    if audio.status == "cancelled":
        return "Generarea audio automată a fost oprită."
    return "Audio indisponibil momentan."


def author_audio_status_message(audio: Optional[models.PostAudio]) -> str:
    if not audio:
        return "Nu ai încărcat încă o lectură de autor pentru acest text."
    if audio.status in ("pending", "processing"):
        return "Înregistrarea audio este în curs de transcriere și moderare."
    if audio.status == "ready":
        return "Lectura ta de autor este publicată."
    if audio.status == "flagged":
        return "Lectura ta este în revizuire."
    if audio.status == "rejected":
        return "Lectura ta a fost respinsă."
    if audio.status == "failed":
        return "Procesarea înregistrării audio a eșuat."
    if audio.status == "cancelled":
        return "Această încărcare a fost înlocuită."
    return audio_status_message(audio)


def post_audio_summary(db: Session, post: models.Post) -> dict:
    audio = crud.get_best_audio_for_post(db, post.id)
    latest = audio or crud.get_latest_audio_for_post(db, post.id)
    author_audio = crud.get_latest_author_audio_for_post(db, post.id)
    if latest and latest.source == "tts" and latest.requester_user_id is None and latest.status in {"pending", "processing"}:
        latest = None
    latest_status = _effective_tts_audio_status(db, latest)
    return {
        "audio_available": audio is not None,
        "audio_status": latest_status if latest else "missing",
        "audio_source": latest.source if latest else None,
        "audio_id": audio.id if audio else None,
        "audio_playback_url": audio_storage.safe_playback_url(audio) if audio else None,
        "audio_tts_character_count": tts_character_count_for_post(post),
        "author_audio_status": author_audio.status if author_audio else "missing",
        "author_audio_message": author_audio_status_message(author_audio),
    }


def audio_track_payload(
    audio: models.PostAudio,
    current_user: Optional[models.User] = None,
    db: Optional[Session] = None,
) -> dict:
    post = audio.post
    owner = post.owner if post else None
    author_id = owner.id if owner else None
    viewer_following = False
    viewer_friendship_status = "none"
    viewer_friendship_id = None
    if db is not None and current_user and author_id:
        viewer_friendship_status = crud.get_friendship_status_for_viewer(db, current_user.id, author_id)
        if current_user.id != author_id:
            viewer_following = crud.is_following(db, current_user.id, author_id)
            friendship = crud.get_friendship_between(db, current_user.id, author_id)
            viewer_friendship_id = friendship.id if friendship else None

    return {
        "audio_id": audio.id,
        "post_id": post.id,
        "title": post.title,
        "slug": post.slug,
        "author_id": author_id,
        "author_username": owner.username if owner else "",
        "category": post.category,
        "source": audio.source,
        "playback_url": audio_storage.playback_url(audio),
        "content_type": audio.content_type,
        "duration_seconds": audio.duration_seconds,
        "viewer_following": viewer_following,
        "viewer_friendship_status": viewer_friendship_status,
        "viewer_friendship_id": viewer_friendship_id,
    }


def normalize_listen_mode(mode: str | None) -> str:
    value = (mode or "toate").strip()
    if value not in crud.AUDIO_LISTEN_MODES:
        raise AudioListenInvalid("Mod de ascultare invalid.")
    return value


def random_listen_audio_track(
    db: Session,
    user: models.User,
    mode: str,
) -> models.PostAudio:
    if not user or not user.has_audio_access:
        raise AudioListenForbidden("Necesită abonament Cronicar sau Rapsod.")
    normalized_mode = normalize_listen_mode(mode)
    audio = crud.get_random_ready_audio_for_listen_mode(db, normalized_mode)
    if not audio:
        raise AudioListenNotFound("Nu există audio disponibil pentru acest mod.")
    return (
        db.query(models.PostAudio)
        .options(joinedload(models.PostAudio.post).joinedload(models.Post.owner))
        .filter(models.PostAudio.id == audio.id)
        .first()
    ) or audio


def random_author_listen_audio_track(
    db: Session,
    user: models.User,
    username: str,
    mode: str,
) -> models.PostAudio:
    if not user or not user.has_audio_access:
        raise AudioListenForbidden("Necesită abonament Cronicar sau Rapsod.")
    normalized_mode = normalize_listen_mode(mode)
    author = crud.get_user_by_username(db, username=username)
    if not author:
        raise AudioListenNotFound("Autorul nu a fost găsit.")
    audio = crud.get_random_ready_audio_for_author_listen_mode(db, author.id, normalized_mode)
    if not audio:
        raise AudioListenNotFound("Nu există audio disponibil pentru acest autor.")
    return (
        db.query(models.PostAudio)
        .options(joinedload(models.PostAudio.post).joinedload(models.Post.owner))
        .filter(models.PostAudio.id == audio.id)
        .first()
    ) or audio


def audio_playlist_summary_payload(db: Session, playlist: models.AudioPlaylist) -> dict:
    items = getattr(playlist, "items", None)
    item_count = len(items) if items is not None else len(crud.get_audio_playlist_items(db, playlist.id))
    return {
        "id": playlist.id,
        "owner_id": playlist.owner_id,
        "title": playlist.title,
        "item_count": item_count,
        "created_at": playlist.created_at,
        "updated_at": playlist.updated_at,
    }


def audio_playlist_item_payload(db: Session, item: models.AudioPlaylistItem) -> dict:
    post = item.post
    audio = crud.get_best_audio_for_post(db, item.post_id)
    return {
        "id": item.id,
        "playlist_id": item.playlist_id,
        "post_id": item.post_id,
        "position": item.position,
        "title": post.title if post else "",
        "slug": post.slug if post else "",
        "author_id": post.owner.id if post and post.owner else None,
        "author_username": post.owner.username if post and post.owner else "",
        "category": post.category if post else None,
        "audio_available": bool(audio and post and post.moderation_status == "approved"),
        "audio_id": audio.id if audio else None,
        "playback_url": audio_storage.safe_playback_url(audio) if audio else None,
        "created_at": item.created_at,
    }


def audio_playlist_detail_payload(db: Session, playlist: models.AudioPlaylist) -> dict:
    items = crud.get_audio_playlist_items(db, playlist.id)
    return {
        **audio_playlist_summary_payload(db, playlist),
        "items": [audio_playlist_item_payload(db, item) for item in items],
    }


def audio_playlist_playback_payload(
    db: Session,
    playlist: models.AudioPlaylist,
    current_user: Optional[models.User] = None,
) -> dict:
    tracks = []
    for item in crud.get_audio_playlist_items(db, playlist.id):
        post = item.post
        if not post or post.moderation_status != "approved":
            continue
        audio = crud.get_best_audio_for_post(db, post.id)
        if not audio:
            continue
        refreshed = (
            db.query(models.PostAudio)
            .options(joinedload(models.PostAudio.post).joinedload(models.Post.owner))
            .filter(models.PostAudio.id == audio.id)
            .first()
        ) or audio
        tracks.append(audio_track_payload(refreshed, current_user=current_user, db=db))
    return {
        "playlist_id": playlist.id,
        "title": playlist.title,
        "tracks": tracks,
    }


def record_listen_seconds(
    db: Session,
    user: Optional[models.User],
    *,
    event_id: str,
    audio_id: int,
    seconds: int,
    mode: str,
) -> dict:
    normalized_mode = normalize_listen_mode(mode)
    clean_event_id = (event_id or "").strip()
    if not clean_event_id:
        raise AudioListenInvalid("Identificatorul evenimentului lipsește.")
    if seconds < 1 or seconds > 60:
        raise AudioListenInvalid("Numărul de secunde trebuie să fie între 1 și 60.")

    audio = crud.get_ready_audio_for_listen_recording(db, audio_id)
    post = audio.post if audio else None
    if not audio or audio.status != "ready" or not post or post.moderation_status != "approved":
        raise AudioListenNotFound("Audio indisponibil.")
    if normalized_mode != "toate" and post.category != normalized_mode:
        raise AudioListenInvalid("Audio nu aparține modului de ascultare selectat.")

    event, recorded = crud.record_audio_listen_event(
        db,
        event_id=clean_event_id,
        audio=audio,
        listener_user_id=user.id if user else None,
        seconds=int(seconds),
        mode=normalized_mode,
    )
    post = crud.get_post(db, event.post_id)
    owner = crud.get_user_by_id(db, event.content_owner_id)
    return {
        "recorded": recorded,
        "audio_id": event.audio_id,
        "post_id": event.post_id,
        "seconds": event.seconds,
        "mode": event.mode,
        "total_post_seconds": post.seconds_listened if post else 0,
        "total_author_seconds": owner.seconds_listened if owner else 0,
    }
