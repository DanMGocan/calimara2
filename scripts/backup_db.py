#!/usr/bin/env python3
"""Back up the Calimara database and uploaded media to S3-compatible object storage.

Runs daily from calimara-backup.timer. Uses the HETZNER_S3_* settings from .env
(BACKUP_S3_BUCKET overrides the bucket); any S3-compatible provider works.

Database: pg_dump's compressed custom format under backups/db/. Dumps older than
BACKUP_KEEP_DAYS (default 30) are deleted, but the newest BACKUP_KEEP (default 3)
are always kept, so a long run of failed backups never empties the history.
Restore with:  pg_restore --clean --no-owner -d calimara_db <file>.dump

Media: the local audio and profile-media folders are mirrored to backups/media/.
Only new or changed files are uploaded. A file that disappeared locally is moved
to backups/media-deleted/<YYYYMMDD>/ and removed after BACKUP_KEEP_DAYS, so an
accidental wipe of the media folder can be undone for a month. If a whole media
folder is missing, nothing is moved for it at all.
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

STATUS_FILE = PROJECT_ROOT / "logs" / "last_backup.json"
PREFIX = "backups/db/"
MEDIA_PREFIX = "backups/media/"
MEDIA_DELETED_PREFIX = "backups/media-deleted/"
REQUIRED = ("HETZNER_S3_ENDPOINT_URL", "HETZNER_S3_ACCESS_KEY_ID", "HETZNER_S3_SECRET_ACCESS_KEY")


def _write_status(**fields) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    fields["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    STATUS_FILE.write_text(json.dumps(fields), encoding="utf-8")


def _list_all(client, bucket: str, prefix: str) -> list[dict]:
    """Every object under prefix (list_objects_v2 returns at most 1000 per page)."""
    objects: list[dict] = []
    params = {"Bucket": bucket, "Prefix": prefix}
    while True:
        response = client.list_objects_v2(**params)
        objects.extend(response.get("Contents", []) or [])
        token = response.get("NextContinuationToken")
        if not response.get("IsTruncated") or not token:
            return objects
        params["ContinuationToken"] = token


def prune_db_dumps(client, bucket: str, *, now: datetime, keep_days: int, keep_min: int) -> tuple[list[str], list[str]]:
    """Delete dumps older than keep_days, always keeping the newest keep_min. Returns (kept, deleted)."""
    dumps = sorted(
        (obj for obj in _list_all(client, bucket, PREFIX) if obj["Key"].endswith(".dump")),
        key=lambda obj: obj["Key"],
        reverse=True,
    )
    cutoff = now - timedelta(days=keep_days)
    kept, deleted = [], []
    for index, obj in enumerate(dumps):
        if index < keep_min or obj["LastModified"] >= cutoff:
            kept.append(obj["Key"])
        else:
            client.delete_object(Bucket=bucket, Key=obj["Key"])
            deleted.append(obj["Key"])
    return kept, deleted


def media_sources() -> dict[str, Path]:
    from app import audio_storage, profile_media

    return {"audio": audio_storage.local_audio_dir(), "profile-media": profile_media.profile_media_dir()}


def sync_media(client, bucket: str, sources: dict[str, Path], *, now: datetime, keep_days: int) -> dict:
    """Mirror local media folders to backups/media/; see the module docstring for deletions."""
    remote = {obj["Key"]: obj for obj in _list_all(client, bucket, MEDIA_PREFIX)}
    uploaded = moved = files = total_bytes = 0
    seen: set[str] = set()
    present_sources: list[str] = []

    for name, root in sources.items():
        if not root.is_dir():
            continue
        present_sources.append(name)
        for path in sorted(root.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            key = f"{MEDIA_PREFIX}{name}/{path.relative_to(root).as_posix()}"
            seen.add(key)
            stat = path.stat()
            files += 1
            total_bytes += stat.st_size
            existing = remote.get(key)
            modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
            if existing and existing.get("Size") == stat.st_size and existing["LastModified"] >= modified:
                continue
            client.upload_file(str(path), bucket, key)
            uploaded += 1

    day = now.strftime("%Y%m%d")
    for key in sorted(remote):
        source = key[len(MEDIA_PREFIX):].split("/", 1)[0]
        if key in seen or source not in present_sources:
            continue
        target = f"{MEDIA_DELETED_PREFIX}{day}/{key[len(MEDIA_PREFIX):]}"
        client.copy_object(Bucket=bucket, Key=target, CopySource={"Bucket": bucket, "Key": key})
        client.delete_object(Bucket=bucket, Key=key)
        moved += 1

    cutoff_day = (now - timedelta(days=keep_days)).strftime("%Y%m%d")
    purged = 0
    for obj in _list_all(client, bucket, MEDIA_DELETED_PREFIX):
        folder = obj["Key"][len(MEDIA_DELETED_PREFIX):].split("/", 1)[0]
        if folder.isdigit() and len(folder) == 8 and folder < cutoff_day:
            client.delete_object(Bucket=bucket, Key=obj["Key"])
            purged += 1

    return {"files": files, "bytes": total_bytes, "uploaded": uploaded, "moved_to_deleted": moved, "purged": purged}


def backup_database(client, bucket: str, *, now: datetime, keep_days: int, keep_min: int) -> dict:
    db_name = os.getenv("DB_NAME", "calimara_db")
    key = f"{PREFIX}{db_name}-{now.strftime('%Y%m%dT%H%M%SZ')}.dump"
    env = {**os.environ, "PGPASSWORD": os.getenv("DB_PASSWORD", "")}
    with tempfile.TemporaryDirectory(prefix="calimara-backup-") as tmp:
        dump_path = Path(tmp) / "db.dump"
        result = subprocess.run(
            [
                "pg_dump", "--format=custom", "--compress=9", "--no-owner", "--no-privileges",
                "-h", os.getenv("DB_HOST", "localhost"), "-p", os.getenv("DB_PORT", "5432"),
                "-U", os.getenv("DB_USER", ""), "-f", str(dump_path), db_name,
            ],
            env=env, capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError("pg_dump: " + result.stderr.strip()[:500])
        size = dump_path.stat().st_size
        client.upload_file(str(dump_path), bucket, key)
    kept, deleted = prune_db_dumps(client, bucket, now=now, keep_days=keep_days, keep_min=keep_min)
    return {"key": key, "size_bytes": size, "kept": kept, "deleted": len(deleted)}


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
    from app import object_storage

    keep_days = max(1, int(os.getenv("BACKUP_KEEP_DAYS", "30")))
    keep_min = max(1, int(os.getenv("BACKUP_KEEP", "3")))
    bucket = (os.getenv("BACKUP_S3_BUCKET") or os.getenv("HETZNER_S3_BUCKET") or "").strip()
    missing = [name for name in REQUIRED if not (os.getenv(name) or "").strip()]
    if not bucket:
        missing.append("HETZNER_S3_BUCKET")
    if missing:
        message = "object storage not configured: " + ", ".join(missing)
        print(f"Backup FAILED: {message}", file=sys.stderr)
        _write_status(ok=False, error=message)
        return 1

    now = datetime.now(timezone.utc)
    try:
        client = object_storage._s3_client()
    except Exception as exc:
        message = f"storage client: {type(exc).__name__}: {exc}"[:500]
        print(f"Backup FAILED: {message}", file=sys.stderr)
        _write_status(ok=False, error=message, bucket=bucket)
        return 1
    status: dict = {"bucket": bucket}
    errors: list[str] = []

    # Each part runs even if the other fails, so one problem never blocks both backups.
    try:
        db = backup_database(client, bucket, now=now, keep_days=keep_days, keep_min=keep_min)
        status.update(key=db["key"], size_bytes=db["size_bytes"], kept=db["kept"])
        print(f"DB backup OK: s3://{bucket}/{db['key']} ({db['size_bytes'] / 1024:.1f} KiB); "
              f"kept {len(db['kept'])}, deleted {db['deleted']}")
    except Exception as exc:
        errors.append(f"database: {type(exc).__name__}: {exc}"[:500])

    try:
        media = sync_media(client, bucket, media_sources(), now=now, keep_days=keep_days)
        status["media"] = media
        print(f"Media backup OK: {media['files']} files ({media['bytes'] / 1024:.1f} KiB), "
              f"uploaded {media['uploaded']}, moved to media-deleted {media['moved_to_deleted']}, "
              f"purged {media['purged']}")
    except Exception as exc:
        errors.append(f"media: {type(exc).__name__}: {exc}"[:500])

    if errors:
        for error in errors:
            print(f"Backup FAILED: {error}", file=sys.stderr)
        _write_status(ok=False, error="; ".join(errors), **status)
        return 1
    _write_status(ok=True, **status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
