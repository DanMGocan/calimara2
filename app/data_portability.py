from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import audio_storage, crud, models, profile_media, rich_text, schemas
from .repositories.slugs import generate_slug
from .utils import get_avatar_url, get_cover_url, normalize_external_url, post_public_url, validate_social_url, validate_youtube_playlist_url


EXPORT_FORMAT = "calimara-user-export"
EXPORT_VERSION = 1

PROFILE_FIELDS = (
    "subtitle",
    "avatar_seed",
    "cover_seed",
    "location",
    "youtube_playlist_url",
    "facebook_url",
    "instagram_url",
    "tiktok_url",
    "x_url",
    "bluesky_url",
    "paypal_url",
    "patreon_url",
    "buymeacoffee_url",
)

PROFILE_LINK_PLATFORMS = {
    "facebook_url": "facebook",
    "instagram_url": "instagram",
    "tiktok_url": "tiktok",
    "x_url": "x",
    "bluesky_url": "bluesky",
    "paypal_url": "paypal",
    "patreon_url": "patreon",
    "buymeacoffee_url": "buymeacoffee",
}


class DataImportError(ValueError):
    pass


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _naive(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _media_url_if_visible(user: models.User, kind: str) -> Optional[str]:
    config = profile_media.media_kind_config(kind)
    key = getattr(user, f"{config['prefix']}_storage_key", None)
    if not key or not user.is_premium:
        return None
    return profile_media.public_media_url(user.username, kind)


def _profile_payload(user: models.User) -> dict[str, Any]:
    return {field: getattr(user, field, None) for field in PROFILE_FIELDS}


def _media_payload(user: models.User) -> dict[str, Optional[str]]:
    profile_photo_url = _media_url_if_visible(user, "profil")
    cover_photo_url = _media_url_if_visible(user, "coperta")
    cover_seed = user.cover_seed or f"{user.username}-cover-sky"
    return {
        "profile_photo_url": profile_photo_url,
        "cover_photo_url": cover_photo_url,
        "avatar_url": profile_photo_url or get_avatar_url(user, size=160),
        "cover_url": cover_photo_url or get_cover_url(cover_seed),
    }


def _post_counts(db: Session, posts: list[models.Post]) -> tuple[dict[int, int], dict[int, int]]:
    if not posts:
        return {}, {}
    post_ids = [post.id for post in posts]
    like_counts = dict(
        db.query(models.Like.post_id, func.count(models.Like.id))
        .filter(models.Like.post_id.in_(post_ids))
        .group_by(models.Like.post_id)
        .all()
    )
    super_like_counts = dict(
        db.query(models.SuperLike.post_id, func.count(models.SuperLike.id))
        .filter(models.SuperLike.post_id.in_(post_ids))
        .group_by(models.SuperLike.post_id)
        .all()
    )
    return like_counts, super_like_counts


def _audio_payload(db: Session, post: models.Post) -> Optional[dict[str, Any]]:
    audio = crud.get_best_audio_for_post(db, post.id)
    if not audio:
        return None
    extension = audio_storage.extension_for_content_type(audio.content_type)
    filename = f"{post.owner.username if post.owner else 'calimara'}-{post.slug}-audio.{extension}"
    return {
        "playback_url": audio_storage.playback_url(audio),
        "download_url": audio_storage.download_url(audio, filename),
        "source": audio.source,
        "content_type": audio.content_type,
        "duration_seconds": audio.duration_seconds,
    }


def _stable_post_id(user: models.User, post: models.Post) -> str:
    created = _iso(post.created_at) or ""
    return f"post:{user.username}:{post.slug}:{created}"


def export_user_data(db: Session, user: models.User) -> dict[str, Any]:
    posts = (
        db.query(models.Post)
        .filter(
            models.Post.user_id == user.id,
            models.Post.moderation_status == "approved",
        )
        .order_by(models.Post.created_at.asc(), models.Post.id.asc())
        .all()
    )
    like_counts, super_like_counts = _post_counts(db, posts)
    exported_posts = []
    for post in posts:
        exported_posts.append(
            {
                "stable_id": _stable_post_id(user, post),
                "source_id": post.id,
                "title": post.title,
                "slug": post.slug,
                "content": rich_text.sanitize_rich_text(post.content),
                "explanatory_note": post.explanatory_note,
                "category": post.category,
                "created_at": _iso(post.created_at),
                "updated_at": _iso(post.updated_at),
                "public_url": post_public_url(user, post.slug),
                "metrics": {
                    "view_count": int(post.view_count or 0),
                    "likes_count": int(like_counts.get(post.id, 0) or 0),
                    "super_likes_count": int(super_like_counts.get(post.id, 0) or 0),
                },
                "audio": _audio_payload(db, post),
            }
        )
    return {
        "format": EXPORT_FORMAT,
        "version": EXPORT_VERSION,
        "export_id": uuid4().hex,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source_username": user.username,
        "profile": _profile_payload(user),
        "media": _media_payload(user),
        "posts": exported_posts,
    }


def _normalize_link(field: str, value: Optional[str], errors: list[str]) -> Optional[str]:
    normalized = normalize_external_url(value)
    if not normalized:
        return None
    if field == "youtube_playlist_url":
        if not validate_youtube_playlist_url(normalized):
            errors.append("Playlistul YouTube din export nu a fost importat: link invalid.")
            return None
        return normalized
    platform = PROFILE_LINK_PLATFORMS.get(field)
    if platform and not validate_social_url(normalized, platform):
        errors.append(f"Linkul {field} din export nu a fost importat: domeniu invalid.")
        return None
    return normalized


def _apply_profile_import(user: models.User, profile: schemas.DataPortabilityProfile, errors: list[str]) -> bool:
    changed = False
    values = profile.model_dump()
    for field in PROFILE_FIELDS:
        value = values.get(field)
        if field.endswith("_url"):
            value = _normalize_link(field, value, errors)
        if getattr(user, field, None) != value:
            setattr(user, field, value)
            changed = True
    return changed


def _source_stable_id(post: schemas.DataPortabilityPost) -> str:
    if post.stable_id:
        return post.stable_id
    return f"post:{post.slug or generate_slug(post.title)}:{post.created_at or ''}"


def _create_imported_post(db: Session, user: models.User, post_data: schemas.DataPortabilityPost) -> models.Post:
    base_slug = post_data.slug or generate_slug(post_data.title)
    slug = crud.ensure_unique_slug(db, base_slug)
    created_at = _naive(post_data.created_at) or datetime.utcnow()
    updated_at = _naive(post_data.updated_at) or created_at
    post = models.Post(
        user_id=user.id,
        title=post_data.title,
        slug=slug,
        content=post_data.content,
        explanatory_note=post_data.explanatory_note,
        category=post_data.category or "poezie",
        view_count=int(post_data.metrics.view_count or 0),
        moderation_status="approved",
        ai_critic_requested=False,
        created_at=created_at,
        updated_at=updated_at,
    )
    db.add(post)
    db.flush()
    return post


def _existing_own_export_post(
    db: Session,
    user: models.User,
    manifest: schemas.DataExportManifest,
    post_data: schemas.DataPortabilityPost,
    stable_id: str,
) -> Optional[models.Post]:
    if manifest.source_username != user.username and not stable_id.startswith(f"post:{user.username}:"):
        return None
    if not post_data.slug:
        return None
    query = db.query(models.Post).filter(
        models.Post.user_id == user.id,
        models.Post.slug == post_data.slug,
    )
    created_at = _naive(post_data.created_at)
    if created_at is not None:
        query = query.filter(models.Post.created_at == created_at)
    return query.first()


def _add_import_snapshot(
    db: Session,
    *,
    user: models.User,
    post: models.Post,
    import_record: models.UserDataImport,
    manifest: schemas.DataExportManifest,
    post_data: schemas.DataPortabilityPost,
    stable_id: str,
) -> None:
    db.add(
        models.ImportedPostSnapshot(
            user_id=user.id,
            post_id=post.id,
            import_id=import_record.id,
            source_export_id=manifest.export_id,
            source_stable_id=stable_id,
            source_post_id=post_data.source_id,
            source_slug=post_data.slug,
            source_title=post_data.title,
            source_created_at=_naive(post_data.created_at),
            imported_view_count=int(post_data.metrics.view_count or 0),
            imported_likes_count=int(post_data.metrics.likes_count or 0),
            imported_super_likes_count=int(post_data.metrics.super_likes_count or 0),
            public_url=post_data.public_url,
            audio_playback_url=post_data.audio.playback_url if post_data.audio else None,
            audio_download_url=post_data.audio.download_url if post_data.audio else None,
            extra_data={
                "audio": post_data.audio.model_dump() if post_data.audio else None,
                "original_slug": post_data.slug,
            },
        )
    )


def import_user_data(db: Session, user: models.User, manifest: schemas.DataExportManifest) -> schemas.DataImportReport:
    if manifest.format != EXPORT_FORMAT or manifest.version != EXPORT_VERSION:
        raise DataImportError("Fișierul nu este un export Călimara compatibil.")

    errors: list[str] = []
    created_posts: list[schemas.DataImportCreatedPost] = []
    skipped_posts: list[str] = []
    failed = 0

    profile_updated = _apply_profile_import(user, manifest.profile, errors)
    import_record = models.UserDataImport(
        user_id=user.id,
        source_export_id=manifest.export_id,
        source_username=manifest.source_username,
        source_created_at=_naive(manifest.exported_at),
        profile_snapshot=manifest.profile.model_dump(),
        media_snapshot=manifest.media.model_dump(),
    )
    db.add(import_record)
    db.flush()

    for post_data in manifest.posts:
        stable_id = _source_stable_id(post_data)
        exists = (
            db.query(models.ImportedPostSnapshot.id)
            .filter(
                models.ImportedPostSnapshot.user_id == user.id,
                models.ImportedPostSnapshot.source_stable_id == stable_id,
            )
            .first()
        )
        if exists:
            skipped_posts.append(post_data.title)
            continue
        try:
            existing_post = _existing_own_export_post(db, user, manifest, post_data, stable_id)
            if existing_post:
                _add_import_snapshot(
                    db,
                    user=user,
                    post=existing_post,
                    import_record=import_record,
                    manifest=manifest,
                    post_data=post_data,
                    stable_id=stable_id,
                )
                skipped_posts.append(post_data.title)
                continue
            post = _create_imported_post(db, user, post_data)
            _add_import_snapshot(
                db,
                user=user,
                post=post,
                import_record=import_record,
                manifest=manifest,
                post_data=post_data,
                stable_id=stable_id,
            )
            created_posts.append(
                schemas.DataImportCreatedPost(
                    title=post.title,
                    slug=post.slug,
                    source_stable_id=stable_id,
                )
            )
        except Exception as exc:
            failed += 1
            errors.append(f"Nu am putut importa „{post_data.title}”: {exc}")

    try:
        db.add(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DataImportError("Importul a întâlnit date duplicate sau invalide.") from exc
    except Exception:
        db.rollback()
        raise

    message = (
        f"Import finalizat: {len(created_posts)} postări create, "
        f"{len(skipped_posts)} duplicate sărite."
    )
    if failed:
        message += f" {failed} postări au eșuat."
    return schemas.DataImportReport(
        profile_updated=profile_updated,
        posts_created=len(created_posts),
        posts_skipped=len(skipped_posts),
        posts_failed=failed,
        created_posts=created_posts,
        skipped_posts=skipped_posts,
        errors=errors,
        message=message,
    )
