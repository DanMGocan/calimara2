import os
from pathlib import Path
from uuid import uuid4

from . import models


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
    return os.getenv("AUDIO_STORAGE_BACKEND", "local").strip().lower()


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


def _save_local(key: str, content: bytes) -> None:
    path = local_path_for_key(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _save_s3(key: str, content: bytes, content_type: str | None) -> None:
    import boto3

    bucket = _required_env("HETZNER_S3_BUCKET")
    client = _s3_client()
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    client.put_object(Bucket=bucket, Key=key, Body=content, **extra_args)


def local_path_for_key(key: str) -> Path:
    return local_audio_dir() / key


def playback_url(audio: models.PostAudio) -> str:
    if audio.storage_backend == "s3":
        return _presigned_s3_url(audio.storage_key or "")
    return f"/api/audio/stream/{audio.id}"


def _presigned_s3_url(key: str) -> str:
    bucket = _required_env("HETZNER_S3_BUCKET")
    ttl = int(os.getenv("AUDIO_SIGNED_URL_TTL_SECONDS", "600"))
    client = _s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=ttl,
    )


def _s3_client():
    import boto3

    endpoint_url = _required_env("HETZNER_S3_ENDPOINT_URL")
    region_name = os.getenv("HETZNER_S3_REGION", "fsn1")
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region_name,
        aws_access_key_id=_required_env("HETZNER_S3_ACCESS_KEY_ID"),
        aws_secret_access_key=_required_env("HETZNER_S3_SECRET_ACCESS_KEY"),
    )


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required for audio storage")
    return value
