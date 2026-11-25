#!/usr/bin/env python3
"""Back up the Calimara database to Hetzner Object Storage, keeping the newest N dumps.

Runs daily from calimara-backup.timer. Uses the HETZNER_S3_* settings from .env
(BACKUP_S3_BUCKET overrides the bucket). The dump is pg_dump's compressed custom
format; restore with:  pg_restore --clean --no-owner -d calimara_db <file>.dump
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from app import object_storage  # noqa: E402

STATUS_FILE = PROJECT_ROOT / "logs" / "last_backup.json"
PREFIX = "backups/db/"
REQUIRED = ("HETZNER_S3_ENDPOINT_URL", "HETZNER_S3_ACCESS_KEY_ID", "HETZNER_S3_SECRET_ACCESS_KEY")


def _write_status(**fields) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    fields["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    STATUS_FILE.write_text(json.dumps(fields), encoding="utf-8")


def _fail(message: str) -> int:
    print(f"Backup FAILED: {message}", file=sys.stderr)
    _write_status(ok=False, error=message)
    return 1


def main() -> int:
    keep = max(1, int(os.getenv("BACKUP_KEEP", "3")))
    bucket = (os.getenv("BACKUP_S3_BUCKET") or os.getenv("HETZNER_S3_BUCKET") or "").strip()
    missing = [name for name in REQUIRED if not (os.getenv(name) or "").strip()]
    if not bucket:
        missing.append("HETZNER_S3_BUCKET")
    if missing:
        return _fail("object storage not configured: " + ", ".join(missing))

    db_name = os.getenv("DB_NAME", "calimara_db")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"{PREFIX}{db_name}-{stamp}.dump"
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
            return _fail("pg_dump: " + result.stderr.strip()[:500])
        size = dump_path.stat().st_size

        try:
            client = object_storage._s3_client()
            client.upload_file(str(dump_path), bucket, key)
            listed = client.list_objects_v2(Bucket=bucket, Prefix=PREFIX).get("Contents", [])
            dumps = sorted((obj["Key"] for obj in listed if obj["Key"].endswith(".dump")), reverse=True)
            stale = dumps[keep:]
            for old_key in stale:
                client.delete_object(Bucket=bucket, Key=old_key)
        except Exception as exc:  # network/credential errors
            return _fail(f"upload: {type(exc).__name__}: {exc}"[:500])

    kept = dumps[:keep]
    print(f"Backup OK: s3://{bucket}/{key} ({size / 1024:.1f} KiB); kept {len(kept)}, deleted {len(stale)}")
    _write_status(ok=True, key=key, bucket=bucket, size_bytes=size, kept=kept)
    return 0


if __name__ == "__main__":
    sys.exit(main())
