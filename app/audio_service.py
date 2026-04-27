import difflib
import html
import logging
import os
import re
from typing import Optional

import bleach
from sqlalchemy.orm import Session, joinedload

from . import audio_storage, crud, models, moderation

logger = logging.getLogger(__name__)


def audio_enabled() -> bool:
    return os.getenv("AUDIO_ENABLED", "False").lower() in ("true", "1", "yes")


def enqueue_tts_for_post(db: Session, post: models.Post) -> Optional[models.PostAudio]:
    if post.moderation_status != "approved":
        return None
    audio = crud.enqueue_tts_audio_for_post(db, post)
    if audio and audio_enabled() and os.getenv("AUDIO_GENERATION_MODE", "queued").lower() == "inline":
        return generate_tts_audio(db, audio)
    return audio


def process_pending_tts_jobs(db: Session, limit: int = 5) -> int:
    if not audio_enabled():
        return 0
    processed = 0
    for audio in crud.get_pending_tts_audio_jobs(db, limit=limit):
        generate_tts_audio(db, audio)
        processed += 1
    return processed


def generate_tts_audio(db: Session, audio: models.PostAudio) -> models.PostAudio:
    audio = crud.update_post_audio(db, audio.id, status="processing", error_message=None) or audio
    post = (
        db.query(models.Post)
        .options(joinedload(models.Post.owner))
        .filter(models.Post.id == audio.post_id)
        .first()
    )
    if not post:
        return crud.update_post_audio(db, audio.id, status="failed", error_message="Post not found") or audio

    try:
        text = text_for_speech(post)
        if not text:
            raise RuntimeError("Post has no readable text")
        content, content_type = synthesize_text(text)
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
        return crud.update_post_audio(
            db,
            audio.id,
            status="failed",
            error_message=str(exc),
        ) or audio


def text_for_speech(post: models.Post) -> str:
    body = strip_html(post.content)
    return f"{post.title}.\n\n{body}".strip()


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = bleach.clean(value, tags=[], strip=True)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def synthesize_text(text: str) -> tuple[bytes, str]:
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
    for chunk in chunks:
        input_kwargs = {"text": chunk}
        if style_prompt:
            input_kwargs["prompt"] = style_prompt
        response = client.synthesize_speech(
            input=texttospeech.SynthesisInput(**input_kwargs),
            voice=voice,
            audio_config=audio_config,
        )
        audio_parts.append(response.audio_content)
    return b"".join(audio_parts), content_type_for_tts_encoding(encoding_name)


def split_text_for_tts(text: str) -> list[str]:
    max_bytes = int(os.getenv("GOOGLE_TTS_MAX_BYTES", os.getenv("GOOGLE_TTS_MAX_CHARS", "3800")))
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
        source="author",
        status="processing",
        storage_backend=backend,
        storage_key=key,
        content_type=content_type,
        byte_size=byte_size,
        language_code=os.getenv("GOOGLE_STT_LANGUAGE_CODE", "ro-RO"),
    )
    try:
        transcript, confidence = transcribe_audio(content)
        result = moderation.moderate_comment(transcript)
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

    client = SpeechClient()
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
            "requires_audio_tier": True,
            "message": "Postarea nu a fost găsită",
        }
    if post.moderation_status != "approved":
        return {
            "available": False,
            "can_listen": bool(current_user and current_user.has_audio_access),
            "requires_audio_tier": not bool(current_user and current_user.has_audio_access),
            "status": "post_pending",
            "title": post.title,
            "author_username": post.owner.username if post.owner else None,
            "message": "Audio disponibil după aprobarea postării",
        }
    audio = crud.get_best_audio_for_post(db, post_id)
    latest = audio or crud.get_latest_audio_for_post(db, post_id)
    can_listen = bool(current_user and current_user.has_audio_access)
    payload = {
        "available": audio is not None,
        "can_listen": can_listen,
        "requires_audio_tier": not can_listen,
        "status": latest.status if latest else "missing",
        "source": latest.source if latest else None,
        "audio_id": audio.id if audio else None,
        "playback_url": audio_storage.playback_url(audio) if audio and can_listen else None,
        "content_type": audio.content_type if audio else None,
        "title": post.title,
        "author_username": post.owner.username if post.owner else None,
    }
    if audio and not can_listen:
        payload["message"] = "Necesită Membru Junimea"
    return payload


def audio_track_payload(audio: models.PostAudio) -> dict:
    post = audio.post
    return {
        "audio_id": audio.id,
        "post_id": post.id,
        "title": post.title,
        "slug": post.slug,
        "author_username": post.owner.username if post.owner else "",
        "source": audio.source,
        "playback_url": audio_storage.playback_url(audio),
        "content_type": audio.content_type,
    }
