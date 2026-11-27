"""Tests for scripts/backup_db.py: DB dump retention and media mirroring."""

import importlib.util
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backup_db.py"
spec = importlib.util.spec_from_file_location("backup_db_under_test", SCRIPT)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)

NOW = datetime(2026, 11, 27, 3, 30, tzinfo=timezone.utc)
BUCKET = "calimara"


class FakeS3:
    """Minimal in-memory S3 client covering the calls the backup script makes."""

    def __init__(self, page_size: int = 1000):
        self.objects: dict[str, dict] = {}
        self.page_size = page_size
        self.uploads: list[str] = []

    def put(self, key: str, body: bytes = b"x", modified: datetime = NOW) -> None:
        self.objects[key] = {"Key": key, "Body": body, "Size": len(body), "LastModified": modified}

    def upload_file(self, filename, bucket, key):
        assert bucket == BUCKET
        self.put(key, Path(filename).read_bytes(), datetime.now(timezone.utc))
        self.uploads.append(key)

    def list_objects_v2(self, Bucket, Prefix="", ContinuationToken=None):
        keys = sorted(k for k in self.objects if k.startswith(Prefix))
        start = int(ContinuationToken or 0)
        page = keys[start:start + self.page_size]
        more = start + self.page_size < len(keys)
        response = {"Contents": [dict(self.objects[k]) for k in page], "IsTruncated": more}
        if more:
            response["NextContinuationToken"] = str(start + self.page_size)
        return response

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)

    def copy_object(self, Bucket, Key, CopySource):
        source = self.objects[CopySource["Key"]]
        self.put(Key, source["Body"], NOW)


def _dump_key(days_ago: int) -> str:
    return f"backups/db/calimara_db-{(NOW - timedelta(days=days_ago)).strftime('%Y%m%dT%H%M%SZ')}.dump"


def test_prune_keeps_30_days_of_dumps():
    s3 = FakeS3()
    for days_ago in range(40):
        s3.put(_dump_key(days_ago), modified=NOW - timedelta(days=days_ago))

    kept, deleted = backup.prune_db_dumps(s3, BUCKET, now=NOW, keep_days=30, keep_min=3)

    assert len(kept) == 31  # today plus 30 days back
    assert len(deleted) == 9
    assert _dump_key(30) in s3.objects and _dump_key(31) not in s3.objects


def test_prune_always_keeps_newest_dumps_even_if_old():
    s3 = FakeS3()
    for days_ago in (60, 61, 62, 63):
        s3.put(_dump_key(days_ago), modified=NOW - timedelta(days=days_ago))

    kept, deleted = backup.prune_db_dumps(s3, BUCKET, now=NOW, keep_days=30, keep_min=3)

    assert kept == [_dump_key(60), _dump_key(61), _dump_key(62)]
    assert deleted == [_dump_key(63)]


def test_prune_lists_past_one_page():
    s3 = FakeS3(page_size=2)
    for days_ago in range(5):
        s3.put(_dump_key(days_ago + 40), modified=NOW - timedelta(days=days_ago + 40))

    kept, deleted = backup.prune_db_dumps(s3, BUCKET, now=NOW, keep_days=30, keep_min=1)

    assert len(kept) == 1 and len(deleted) == 4


def _media(tmp_path: Path) -> dict[str, Path]:
    audio = tmp_path / "audio"
    (audio / "posts" / "1").mkdir(parents=True)
    (audio / "posts" / "1" / "tts.mp3").write_bytes(b"audio-1")
    (audio / "posts" / "2.wav").write_bytes(b"audio-2")
    profile = tmp_path / "profile-media"
    (profile / "users" / "7").mkdir(parents=True)
    (profile / "users" / "7" / "avatar.webp").write_bytes(b"avatar")
    return {"audio": audio, "profile-media": profile}


def test_sync_uploads_all_files_then_only_changes(tmp_path):
    sources = _media(tmp_path)
    s3 = FakeS3()

    first = backup.sync_media(s3, BUCKET, sources, now=NOW, keep_days=30)
    assert first["uploaded"] == 3 and first["files"] == 3
    assert "backups/media/audio/posts/1/tts.mp3" in s3.objects
    assert "backups/media/profile-media/users/7/avatar.webp" in s3.objects

    s3.uploads.clear()
    second = backup.sync_media(s3, BUCKET, sources, now=NOW, keep_days=30)
    assert second["uploaded"] == 0 and s3.uploads == []

    changed = sources["audio"] / "posts" / "2.wav"
    changed.write_bytes(b"regenerated audio")
    third = backup.sync_media(s3, BUCKET, sources, now=NOW, keep_days=30)
    assert s3.uploads == ["backups/media/audio/posts/2.wav"]
    assert s3.objects["backups/media/audio/posts/2.wav"]["Body"] == b"regenerated audio"
    assert third["uploaded"] == 1


def test_same_size_rewrite_is_uploaded_when_newer(tmp_path):
    sources = _media(tmp_path)
    s3 = FakeS3()
    backup.sync_media(s3, BUCKET, sources, now=NOW, keep_days=30)
    s3.objects["backups/media/audio/posts/2.wav"]["LastModified"] = datetime(2020, 1, 1, tzinfo=timezone.utc)

    path = sources["audio"] / "posts" / "2.wav"
    path.write_bytes(b"AUDIO-2")  # same length as before
    s3.uploads.clear()
    backup.sync_media(s3, BUCKET, sources, now=NOW, keep_days=30)

    assert s3.uploads == ["backups/media/audio/posts/2.wav"]


def test_deleted_file_moves_to_dated_trash_and_expires(tmp_path):
    sources = _media(tmp_path)
    s3 = FakeS3()
    backup.sync_media(s3, BUCKET, sources, now=NOW, keep_days=30)

    (sources["audio"] / "posts" / "2.wav").unlink()
    result = backup.sync_media(s3, BUCKET, sources, now=NOW, keep_days=30)

    trashed = "backups/media-deleted/20261127/audio/posts/2.wav"
    assert result["moved_to_deleted"] == 1
    assert "backups/media/audio/posts/2.wav" not in s3.objects
    assert s3.objects[trashed]["Body"] == b"audio-2"

    later = backup.sync_media(s3, BUCKET, sources, now=NOW + timedelta(days=30), keep_days=30)
    assert later["purged"] == 0 and trashed in s3.objects
    expired = backup.sync_media(s3, BUCKET, sources, now=NOW + timedelta(days=31), keep_days=30)
    assert expired["purged"] == 1 and trashed not in s3.objects


def test_missing_media_folder_never_touches_its_backup(tmp_path):
    sources = _media(tmp_path)
    s3 = FakeS3()
    backup.sync_media(s3, BUCKET, sources, now=NOW, keep_days=30)

    wiped = {"audio": tmp_path / "gone", "profile-media": sources["profile-media"]}
    result = backup.sync_media(s3, BUCKET, wiped, now=NOW, keep_days=30)

    assert result["moved_to_deleted"] == 0
    assert "backups/media/audio/posts/1/tts.mp3" in s3.objects
    assert "backups/media/audio/posts/2.wav" in s3.objects


def test_symlinks_are_not_backed_up(tmp_path):
    sources = _media(tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("do not upload")
    os.symlink(secret, sources["audio"] / "link.mp3")
    s3 = FakeS3()

    backup.sync_media(s3, BUCKET, sources, now=NOW, keep_days=30)

    assert "backups/media/audio/link.mp3" not in s3.objects


def test_media_defaults_live_outside_temp(monkeypatch):
    from app import audio_storage, profile_media

    monkeypatch.delenv("AUDIO_LOCAL_DIR", raising=False)
    monkeypatch.delenv("PROFILE_MEDIA_LOCAL_DIR", raising=False)
    root = Path(audio_storage.__file__).resolve().parents[1]

    assert audio_storage.local_audio_dir() == root / "media" / "audio"
    assert profile_media.profile_media_dir() == root / "media" / "profile-media"


@pytest.mark.parametrize("name", ["audio", "profile-media"])
def test_media_sources_match_storage_modules(monkeypatch, tmp_path, name):
    monkeypatch.setenv("AUDIO_LOCAL_DIR", str(tmp_path / "a"))
    monkeypatch.setenv("PROFILE_MEDIA_LOCAL_DIR", str(tmp_path / "p"))
    sources = backup.media_sources()
    assert sources[name] == tmp_path / ("a" if name == "audio" else "p")
