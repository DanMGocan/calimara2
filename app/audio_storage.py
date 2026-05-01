import os
from pathlib import Path
from uuid import uuid4

from . import models, object_storage


PROJECT_ROOT = Path(__file__).resolve().parent.parent


CONTENT_TYPE_EXTENSIONS = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
}


def storage_backend() -> str:
    return object_storage.storage_backend("AUDIO_STORAGE_BACKEND")


def local_audio_dir() -> Path:
    configured = os.getenv("AUDIO_LOCAL_DIR", "temp/audio")
    path = Path(configured)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def extension_for_content_type(content_type: str | None) -> str:
    if not content_type:
        return "bin"
    return CONTENT_TYPE_EXTENSIONS.get(content_type.split(";")[0].strip().lower(), "bin")


def build_storage_key(post_id: int, source: str, content_type: str | None) -> str:
    ext = extension_for_content_type(content_type)
    return f"posts/{post_id}/audio/{source}-{uuid4().hex}.{ext}"


def save_audio_bytes(
    *, post_id: int, source: str, content: bytes, content_type: str | None
) -> tuple[str, str, int]:
    backend = storage_backend()
    key = build_storage_key(post_id, source, content_type)
    if backend == "s3":
        _save_s3(key, content, content_type)
    else:
        _save_local(key, content)
        backend = "local"
    return backend, key, len(content)


def load_audio_bytes(audio: models.PostAudio) -> bytes:
    if not audio.storage_key:
        raise RuntimeError("Audio storage key is missing")
    if audio.storage_backend == "s3":
        return object_storage.get_object_bytes(audio.storage_key)
    path = local_path_for_key(audio.storage_key)
    if not path.exists():
        raise RuntimeError("Audio file is missing from local storage")
    return path.read_bytes()


def _save_local(key: str, content: bytes) -> None:
    path = local_path_for_key(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _save_s3(key: str, content: bytes, content_type: str | None) -> None:
    object_storage.put_object(key, content, content_type)


def local_path_for_key(key: str) -> Path:
    return local_audio_dir() / key


def playback_url(audio: models.PostAudio) -> str:
    if audio.storage_backend == "s3":
        return _presigned_s3_url(audio.storage_key or "")
    return f"/api/audio/redare/{audio.id}"


def download_url(audio: models.PostAudio, filename: str) -> str:
    if audio.storage_backend == "s3":
        return _presigned_s3_url(
            audio.storage_key or "",
            content_disposition=f'attachment; filename="{filename}"',
        )
    return f"/api/audio/descarcare/{audio.id}"


def _presigned_s3_url(key: str, content_disposition: str | None = None) -> str:
    ttl = int(os.getenv("AUDIO_SIGNED_URL_TTL_SECONDS", str(object_storage.signed_url_ttl_seconds())))
    return object_storage.presigned_get_url(
        key,
        content_disposition=content_disposition,
        ttl_seconds=ttl,
    )
