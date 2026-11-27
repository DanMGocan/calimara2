import logging
import os
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

try:
    import pillow_avif  # noqa: F401
except Exception:
    pillow_avif = None

from . import object_storage


PROJECT_ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)
PROFILE_MEDIA_CONTENT_TYPE = "image/webp"
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/avif",
}
MEDIA_KINDS = {
    "profil": {
        "prefix": "profile_photo",
        "size": (512, 512),
        "label": "fotografia de profil",
    },
    "coperta": {
        "prefix": "cover_photo",
        "size": (1600, 600),
        "label": "fotografia de copertă",
    },
}


def profile_media_dir() -> Path:
    configured = os.getenv("PROFILE_MEDIA_LOCAL_DIR", "media/profile-media")
    path = Path(configured)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def storage_backend() -> str:
    return object_storage.storage_backend("PROFILE_MEDIA_STORAGE_BACKEND")


def media_kind_config(kind: str) -> dict:
    config = MEDIA_KINDS.get(kind)
    if not config:
        raise HTTPException(status_code=404, detail="Tip de imagine necunoscut")
    return config


def max_upload_bytes() -> int:
    max_mb = int(os.getenv("PROFILE_MEDIA_UPLOAD_MAX_MB", "8"))
    return max_mb * 1024 * 1024


def build_storage_key(user_id: int, kind: str) -> str:
    return f"users/{user_id}/{kind}-{uuid4().hex}.webp"


def build_club_storage_key(club_id: int, kind: str) -> str:
    return f"clubs/{club_id}/{kind}-{uuid4().hex}.webp"


def local_path_for_key(key: str) -> Path:
    return profile_media_dir() / key


def public_media_url(username: str, kind: str) -> str:
    return f"/api/utilizatori/{username}/media/{kind}"


def public_club_media_url(slug: str, kind: str) -> str:
    return f"/api/cluburi/{slug}/media/{kind}"


def save_profile_media_bytes(*, user_id: int, kind: str, content: bytes) -> tuple[str, str, str]:
    key = build_storage_key(user_id, kind)
    backend = storage_backend()
    if backend == "s3":
        object_storage.put_object(key, content, PROFILE_MEDIA_CONTENT_TYPE)
        return "s3", key, PROFILE_MEDIA_CONTENT_TYPE
    path = local_path_for_key(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return "local", key, PROFILE_MEDIA_CONTENT_TYPE


def save_club_media_bytes(*, club_id: int, kind: str, content: bytes) -> tuple[str, str, str]:
    key = build_club_storage_key(club_id, kind)
    backend = storage_backend()
    if backend == "s3":
        object_storage.put_object(key, content, PROFILE_MEDIA_CONTENT_TYPE)
        return "s3", key, PROFILE_MEDIA_CONTENT_TYPE
    path = local_path_for_key(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return "local", key, PROFILE_MEDIA_CONTENT_TYPE


def delete_local_media(key: str | None) -> None:
    if not key:
        return
    path = local_path_for_key(key)
    try:
        path.unlink()
    except FileNotFoundError:
        return


def delete_stored_media(backend: str | None, key: str | None) -> None:
    if backend == "s3":
        try:
            object_storage.delete_object(key)
        except Exception:
            logger.warning("Failed to delete profile media object %s", key, exc_info=True)
    elif backend == "local":
        delete_local_media(key)


def presigned_media_url(key: str) -> str:
    ttl = int(
        os.getenv(
            "PROFILE_MEDIA_SIGNED_URL_TTL_SECONDS",
            os.getenv("HETZNER_S3_SIGNED_URL_TTL_SECONDS", "600"),
        )
    )
    return object_storage.presigned_get_url(key, ttl_seconds=ttl)


def process_uploaded_image(content: bytes, kind: str) -> bytes:
    config = media_kind_config(kind)
    try:
        image = Image.open(BytesIO(content))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(status_code=400, detail="Fișierul încărcat nu este o imagine validă")

    image = ImageOps.exif_transpose(image)
    image = ImageOps.fit(image, config["size"], method=Image.Resampling.LANCZOS)
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA")

    output = BytesIO()
    image.save(output, format="WEBP", quality=86, method=6)
    return output.getvalue()
