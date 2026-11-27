"""Delete stored media files once the platform no longer uses them.

Two layers:

1. A session hook. Whenever a flush deletes a PostAudio, Post, User or Club, or
   replaces an audio file or a profile/cover photo, the files involved are
   remembered. After the transaction commits, each one that no database row
   still references is deleted (local disk or S3). A rollback forgets them.
   Bulk `query.delete()` calls skip ORM hooks; call `mark_user_media` (or
   `mark_media`) before such a delete to include them.

2. A nightly sweep (`sweep_unreferenced_local_files`, run from
   scripts/backup_db.py) that deletes any local file older than a day that no
   row references, as a safety net for paths the hook cannot see.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import event, inspect, or_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

AUDIO = "audio"
PROFILE_MEDIA = "profile-media"
_PENDING = "media_cleanup_pending"
_PHOTO_FIELDS = (
    ("profile_photo_storage_backend", "profile_photo_storage_key"),
    ("cover_photo_storage_backend", "cover_photo_storage_key"),
)
_BACKENDS = ("local", "s3")


def _pending(session: Session) -> set[tuple[str, str, str]]:
    return session.info.setdefault(_PENDING, set())


def mark_media(session: Session, kind: str, backend: str | None, key: str | None) -> None:
    """Delete this file after the current transaction commits, if nothing references it then."""
    if backend in _BACKENDS and key:
        _pending(session).add((kind, backend, key))


def _models():
    from app import models

    return models


def _mark_post_audio(session: Session, post_filter) -> None:
    models = _models()
    rows = session.query(models.PostAudio.storage_backend, models.PostAudio.storage_key).filter(post_filter)
    for backend, key in rows:
        mark_media(session, AUDIO, backend, key)


def _mark_photos(session: Session, model, row_filter) -> None:
    columns = [getattr(model, name) for pair in _PHOTO_FIELDS for name in pair]
    for row in session.query(*columns).filter(row_filter):
        mark_media(session, PROFILE_MEDIA, row[0], row[1])
        mark_media(session, PROFILE_MEDIA, row[2], row[3])


def mark_user_media(session: Session, user_id: int) -> None:
    """Everything deleting this user takes with it: post audio, own photos, owned clubs' photos."""
    models = _models()
    with session.no_autoflush:
        post_ids = session.query(models.Post.id).filter(models.Post.user_id == user_id)
        _mark_post_audio(session, models.PostAudio.post_id.in_(post_ids.scalar_subquery()))
        _mark_photos(session, models.User, models.User.id == user_id)
        _mark_photos(session, models.Club, models.Club.owner_id == user_id)


def _committed(obj, attr: str):
    """The attribute's value as stored in the database (before pending changes)."""
    history = inspect(obj).attrs[attr].history
    if history.deleted:
        return history.deleted[0]
    if history.unchanged:
        return history.unchanged[0]
    return getattr(obj, attr, None) if not history.added else None


def _replaced(session: Session, obj, backend_attr: str, key_attr: str) -> tuple[str | None, str | None] | None:
    """(old_backend, old_key) if this flush replaces the stored file, else None.

    The old values are read from the database: an object loaded in an earlier
    transaction does not keep them in its attribute history.
    """
    state = inspect(obj)
    if not (state.attrs[key_attr].history.has_changes() or state.attrs[backend_attr].history.has_changes()):
        return None
    model = type(obj)
    old = (
        session.query(getattr(model, backend_attr), getattr(model, key_attr))
        .filter(model.id == obj.id)
        .first()
    )
    if old is None:
        return None
    old = (old[0], old[1])
    new = (getattr(obj, backend_attr), getattr(obj, key_attr))
    return old if old != new else None


def _before_flush(session: Session, flush_context, instances) -> None:
    models = _models()
    with session.no_autoflush:
        for obj in list(session.deleted):
            if isinstance(obj, models.PostAudio):
                mark_media(session, AUDIO, _committed(obj, "storage_backend"), _committed(obj, "storage_key"))
            elif isinstance(obj, models.Post) and obj.id is not None:
                _mark_post_audio(session, models.PostAudio.post_id == obj.id)
            elif isinstance(obj, models.User) and obj.id is not None:
                mark_user_media(session, obj.id)
            elif isinstance(obj, models.Club) and obj.id is not None:
                for backend_attr, key_attr in _PHOTO_FIELDS:
                    mark_media(session, PROFILE_MEDIA, _committed(obj, backend_attr), _committed(obj, key_attr))

        for obj in list(session.dirty):
            if isinstance(obj, models.PostAudio):
                old = _replaced(session, obj, "storage_backend", "storage_key")
                if old:
                    mark_media(session, AUDIO, *old)
            elif isinstance(obj, (models.User, models.Club)):
                for backend_attr, key_attr in _PHOTO_FIELDS:
                    old = _replaced(session, obj, backend_attr, key_attr)
                    if old:
                        mark_media(session, PROFILE_MEDIA, *old)


def _still_referenced(bind, files: set[tuple[str, str, str]]) -> set[tuple[str, str, str]]:
    models = _models()
    audio_keys = {key for kind, _, key in files if kind == AUDIO}
    photo_keys = {key for kind, _, key in files if kind == PROFILE_MEDIA}
    used: set[tuple[str, str, str]] = set()
    with Session(bind=bind) as check:
        if audio_keys:
            for backend, key in check.query(models.PostAudio.storage_backend, models.PostAudio.storage_key).filter(
                models.PostAudio.storage_key.in_(audio_keys)
            ):
                used.add((AUDIO, backend, key))
        if photo_keys:
            for model in (models.User, models.Club):
                for backend_attr, key_attr in _PHOTO_FIELDS:
                    backend_col, key_col = getattr(model, backend_attr), getattr(model, key_attr)
                    for backend, key in check.query(backend_col, key_col).filter(key_col.in_(photo_keys)):
                        used.add((PROFILE_MEDIA, backend, key))
    return used


def _local_root(kind: str) -> Path:
    from app import audio_storage, profile_media

    return audio_storage.local_audio_dir() if kind == AUDIO else profile_media.profile_media_dir()


def delete_file(kind: str, backend: str, key: str) -> bool:
    """Delete one stored file. Never raises; returns True if something was removed."""
    try:
        if backend == "s3":
            from app import object_storage

            object_storage.delete_object(key)
            return True
        root = _local_root(kind).resolve()
        path = (root / key).resolve()
        if not path.is_relative_to(root) or path == root:
            logger.warning("Refusing to delete %s media outside its folder: %r", kind, key)
            return False
        path.unlink()
        _prune_empty_dirs(path.parent, root)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        logger.warning("Could not delete %s media %s:%s", kind, backend, key, exc_info=True)
        return False


def _prune_empty_dirs(folder: Path, root: Path) -> None:
    while folder != root and folder.is_relative_to(root):
        try:
            folder.rmdir()
        except OSError:
            return
        folder = folder.parent


def _after_commit(session: Session) -> None:
    files = session.info.pop(_PENDING, None)
    if not files:
        return
    try:
        used = _still_referenced(session.get_bind(), files)
    except Exception:
        logger.warning("Media cleanup skipped: could not check references", exc_info=True)
        return
    for kind, backend, key in sorted(files - used):
        if delete_file(kind, backend, key):
            logger.info("Deleted unused %s media %s:%s", kind, backend, key)


def _after_rollback(session: Session) -> None:
    session.info.pop(_PENDING, None)


def register() -> None:
    if not event.contains(Session, "before_flush", _before_flush):
        event.listen(Session, "before_flush", _before_flush)
        event.listen(Session, "after_commit", _after_commit)
        event.listen(Session, "after_rollback", _after_rollback)


# ---------------------------------------------------------------------------
# Nightly sweep


def referenced_media_keys(session: Session) -> dict[str, set[str]]:
    """Storage keys of every local file the database still uses, per media kind."""
    models = _models()
    audio = {
        key
        for (key,) in session.query(models.PostAudio.storage_key).filter(
            models.PostAudio.storage_backend == "local", models.PostAudio.storage_key.isnot(None)
        )
    }
    photos: set[str] = set()
    for model in (models.User, models.Club):
        columns = [getattr(model, name) for pair in _PHOTO_FIELDS for name in pair]
        for row in session.query(*columns).filter(or_(columns[0] == "local", columns[2] == "local")):
            if row[0] == "local" and row[1]:
                photos.add(row[1])
            if row[2] == "local" and row[3]:
                photos.add(row[3])
    return {AUDIO: audio, PROFILE_MEDIA: photos}


def sweep_unreferenced_local_files(
    referenced: dict[str, set[str]],
    sources: dict[str, Path],
    *,
    now: datetime | None = None,
    min_age_hours: float = 24,
    max_fraction: float = 0.5,
    min_guard_files: int = 5,
) -> dict:
    """Delete local files older than min_age_hours that no row references.

    Guard: if a folder would lose more than max_fraction of its files (and more
    than min_guard_files), nothing in it is deleted and it is reported instead,
    because that looks like a bug or a broken database rather than cleanup.
    """
    now = now or datetime.now(timezone.utc)
    report = {"deleted": 0, "deleted_bytes": 0, "skipped_folders": []}
    for kind, root in sources.items():
        if not root.is_dir():
            continue
        files = [p for p in root.rglob("*") if p.is_file() and not p.is_symlink()]
        keep = referenced.get(kind, set())
        doomed = []
        for path in files:
            if path.relative_to(root).as_posix() in keep:
                continue
            age_hours = (now - datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)).total_seconds() / 3600
            if age_hours >= min_age_hours:
                doomed.append(path)
        if len(doomed) > min_guard_files and len(doomed) > max_fraction * len(files):
            report["skipped_folders"].append(f"{kind}: {len(doomed)} of {len(files)} files unreferenced")
            continue
        for path in doomed:
            size = path.stat().st_size
            if delete_file(kind, "local", path.relative_to(root).as_posix()):
                report["deleted"] += 1
                report["deleted_bytes"] += size
    return report
