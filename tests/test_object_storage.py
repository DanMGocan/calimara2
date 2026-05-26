from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import audio_storage, models, object_storage, profile_media
from app import schemas
from app.routers import admin_routes, user_routes
from app.week_util import utcnow_naive


class FakeBody:
    def __init__(self, content: bytes):
        self.content = content

    def read(self) -> bytes:
        return self.content


class FakeS3Client:
    def __init__(self):
        self.objects = {}
        self.presigned_requests = []

    def put_object(self, **kwargs):
        self.objects[kwargs["Key"]] = kwargs

    def get_object(self, **kwargs):
        return {"Body": FakeBody(self.objects[kwargs["Key"]]["Body"])}

    def delete_object(self, **kwargs):
        self.objects.pop(kwargs["Key"], None)

    def list_objects_v2(self, **kwargs):
        prefix = kwargs.get("Prefix") or ""
        max_keys = kwargs.get("MaxKeys") or 1000
        cursor = kwargs.get("ContinuationToken")
        keys = sorted(key for key in self.objects if key.startswith(prefix))
        start = keys.index(cursor) if cursor in keys else 0
        selected = keys[start:start + max_keys]
        next_cursor = keys[start + max_keys] if start + max_keys < len(keys) else None
        return {
            "Contents": [
                {
                    "Key": key,
                    "Size": len(self.objects[key].get("Body") or b""),
                    "LastModified": self.objects[key].get("LastModified") or datetime(2026, 5, 19, tzinfo=timezone.utc),
                    "ETag": self.objects[key].get("ETag") or f'"etag-{key}"',
                    "StorageClass": self.objects[key].get("StorageClass") or "STANDARD",
                }
                for key in selected
            ],
            "IsTruncated": next_cursor is not None,
            "NextContinuationToken": next_cursor,
        }

    def head_object(self, **kwargs):
        item = self.objects[kwargs["Key"]]
        return {
            "ContentLength": len(item.get("Body") or b""),
            "ContentType": item.get("ContentType"),
            "ETag": item.get("ETag") or f'"etag-{kwargs["Key"]}"',
            "LastModified": item.get("LastModified") or datetime(2026, 5, 19, tzinfo=timezone.utc),
        }

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        self.presigned_requests.append(
            {"operation": operation, "params": Params, "expires_in": ExpiresIn}
        )
        return f"https://signed.test/{Params['Bucket']}/{Params['Key']}?ttl={ExpiresIn}"


def set_s3_env(monkeypatch, fake_client: FakeS3Client):
    monkeypatch.setenv("HETZNER_S3_BUCKET", "calimara")
    monkeypatch.setenv("HETZNER_S3_ENDPOINT_URL", "https://fsn1.your-objectstorage.com")
    monkeypatch.setenv("HETZNER_S3_REGION", "fsn1")
    monkeypatch.setenv("HETZNER_S3_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("HETZNER_S3_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setattr(object_storage, "_s3_client", lambda: fake_client)


def test_audio_storage_saves_loads_and_signs_s3_objects(monkeypatch):
    fake_client = FakeS3Client()
    set_s3_env(monkeypatch, fake_client)
    monkeypatch.setenv("AUDIO_STORAGE_BACKEND", "s3")
    monkeypatch.setenv("AUDIO_SIGNED_URL_TTL_SECONDS", "123")

    backend, key, byte_size = audio_storage.save_audio_bytes(
        post_id=10,
        source="author",
        content=b"audio-bytes",
        content_type="audio/mpeg",
    )

    assert backend == "s3"
    assert key.startswith("posts/10/audio/author-")
    assert byte_size == len(b"audio-bytes")
    assert fake_client.objects[key]["Bucket"] == "calimara"
    assert fake_client.objects[key]["ContentType"] == "audio/mpeg"

    audio = models.PostAudio(
        id=99,
        post_id=10,
        source="author",
        status="ready",
        storage_backend="s3",
        storage_key=key,
        content_type="audio/mpeg",
    )
    assert audio_storage.load_audio_bytes(audio) == b"audio-bytes"

    signed_url = audio_storage.download_url(audio, "author-poem-audio.mp3")
    assert signed_url == f"https://signed.test/calimara/{key}?ttl=123"
    assert fake_client.presigned_requests[-1]["params"]["ResponseContentDisposition"] == (
        'attachment; filename="author-poem-audio.mp3"'
    )


def test_profile_media_saves_signs_and_deletes_s3_objects(monkeypatch):
    fake_client = FakeS3Client()
    set_s3_env(monkeypatch, fake_client)
    monkeypatch.setenv("PROFILE_MEDIA_STORAGE_BACKEND", "s3")
    monkeypatch.setenv("PROFILE_MEDIA_SIGNED_URL_TTL_SECONDS", "321")

    backend, key, content_type = profile_media.save_profile_media_bytes(
        user_id=42,
        kind="profil",
        content=b"webp-bytes",
    )

    assert backend == "s3"
    assert key.startswith("users/42/profil-")
    assert content_type == profile_media.PROFILE_MEDIA_CONTENT_TYPE
    assert fake_client.objects[key]["Bucket"] == "calimara"
    assert fake_client.objects[key]["ContentType"] == profile_media.PROFILE_MEDIA_CONTENT_TYPE

    signed_url = profile_media.presigned_media_url(key)
    assert signed_url == f"https://signed.test/calimara/{key}?ttl=321"

    profile_media.delete_stored_media("s3", key)
    assert key not in fake_client.objects


def test_object_storage_lists_objects_with_cursor(monkeypatch):
    fake_client = FakeS3Client()
    set_s3_env(monkeypatch, fake_client)
    fake_client.objects = {
        "posts/a.mp3": {"Body": b"a"},
        "posts/b.mp3": {"Body": b"bb"},
        "users/1/profil.webp": {"Body": b"webp"},
    }

    first = object_storage.list_objects(prefix="posts/", max_keys=1)
    second = object_storage.list_objects(prefix="posts/", max_keys=1, continuation_token=first["next_cursor"])

    assert [item["Key"] for item in first["objects"]] == ["posts/a.mp3"]
    assert first["next_cursor"] == "posts/b.mp3"
    assert [item["Key"] for item in second["objects"]] == ["posts/b.mp3"]
    assert second["next_cursor"] is None


def test_admin_storage_dashboard_marks_references_and_deletes_safe_objects(monkeypatch):
    fake_client = FakeS3Client()
    set_s3_env(monkeypatch, fake_client)
    fake_client.objects = {
        "posts/1/audio/ref.mp3": {"Body": b"referenced", "ContentType": "audio/mpeg"},
        "posts/orphan.mp3": {"Body": b"orphan", "ContentType": "audio/mpeg"},
        "misc/outside.bin": {"Body": b"outside", "ContentType": "application/octet-stream"},
    }

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        admin_user = models.User(username="admin", email="admin@example.com", google_id="google-admin", is_admin=True)
        author = models.User(username="author", email="author@example.com", google_id="google-author")
        db.add_all([admin_user, author])
        db.flush()
        post = models.Post(
            user_id=author.id,
            title="Referenced",
            slug="referenced",
            content="content",
            category="poezie",
            moderation_status="approved",
        )
        db.add(post)
        db.flush()
        db.add(
            models.PostAudio(
                post_id=post.id,
                requester_user_id=author.id,
                source="tts",
                status="ready",
                storage_backend="s3",
                storage_key="posts/1/audio/ref.mp3",
                content_type="audio/mpeg",
            )
        )
        db.commit()

        payload = admin_routes.list_admin_storage_objects(status_filter="all", limit=50, db=db, current_user=admin_user)
        objects = {item["key"]: item for item in payload["objects"]}

        assert objects["posts/1/audio/ref.mp3"]["can_delete"] is False
        assert objects["posts/1/audio/ref.mp3"]["references"][0]["type"] == "audio"
        assert objects["posts/orphan.mp3"]["can_delete"] is True
        assert objects["misc/outside.bin"]["can_delete"] is False

        request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))
        with pytest.raises(HTTPException) as referenced_error:
            admin_routes.delete_admin_storage_object(
                schemas.AdminStorageObjectDelete(key="posts/1/audio/ref.mp3", reason="cleanup"),
                request,
                db=db,
                current_user=admin_user,
            )
        assert referenced_error.value.status_code == 409

        with pytest.raises(HTTPException) as outside_error:
            admin_routes.delete_admin_storage_object(
                schemas.AdminStorageObjectDelete(key="misc/outside.bin", reason="cleanup"),
                request,
                db=db,
                current_user=admin_user,
            )
        assert outside_error.value.status_code == 400

        response = admin_routes.delete_admin_storage_object(
            schemas.AdminStorageObjectDelete(key="posts/orphan.mp3", reason="cleanup"),
            request,
            db=db,
            current_user=admin_user,
        )

        assert response == {"success": True, "key": "posts/orphan.mp3"}
        assert "posts/orphan.mp3" not in fake_client.objects
        audit = db.query(models.AdminAuditLog).filter_by(action="storage_object_delete").one()
        assert audit.target_type == "storage_object"
        assert audit.reason == "cleanup"
        assert audit.extra_data["key"] == "posts/orphan.mp3"
    finally:
        db.close()
        models.Base.metadata.drop_all(engine)
        engine.dispose()


def test_admin_storage_cleanup_clears_known_references_and_deletes_object(monkeypatch):
    fake_client = FakeS3Client()
    set_s3_env(monkeypatch, fake_client)
    shared_key = "posts/1/audio/shared.mp3"
    fake_client.objects = {
        shared_key: {"Body": b"shared", "ContentType": "audio/mpeg"},
    }

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        admin_user = models.User(username="admin", email="admin@example.com", google_id="google-admin", is_admin=True)
        author = models.User(
            username="author",
            email="author@example.com",
            google_id="google-author",
            profile_photo_storage_backend="s3",
            profile_photo_storage_key=shared_key,
            profile_photo_content_type="image/webp",
            cover_photo_storage_backend="s3",
            cover_photo_storage_key=shared_key,
            cover_photo_content_type="image/webp",
        )
        db.add_all([admin_user, author])
        db.flush()
        post = models.Post(
            user_id=author.id,
            title="Referenced",
            slug="referenced",
            content="content",
            category="poezie",
            moderation_status="approved",
        )
        db.add(post)
        db.flush()
        club = models.Club(
            owner_id=author.id,
            title="Club",
            slug="club",
            speciality="poezie",
            join_policy="private",
            profile_photo_storage_backend="s3",
            profile_photo_storage_key=shared_key,
            profile_photo_content_type="image/webp",
            cover_photo_storage_backend="s3",
            cover_photo_storage_key=shared_key,
            cover_photo_content_type="image/webp",
        )
        audio = models.PostAudio(
            post_id=post.id,
            requester_user_id=author.id,
            source="tts",
            status="ready",
            storage_backend="s3",
            storage_key=shared_key,
            content_type="audio/mpeg",
            byte_size=6,
            moderation_status="approved",
        )
        db.add_all([club, audio])
        db.commit()

        request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))
        response = admin_routes.cleanup_admin_storage_object(
            schemas.AdminStorageObjectCleanup(key=shared_key, reason="referenced cleanup"),
            request,
            db=db,
            current_user=admin_user,
        )

        assert response["success"] is True
        assert response["key"] == shared_key
        assert response["references_removed"] == 5
        assert {reference["type"] for reference in response["references"]} == {
            "audio",
            "user_profile_photo",
            "user_cover_photo",
            "club_profile_photo",
            "club_cover_photo",
        }
        assert shared_key not in fake_client.objects

        db.refresh(audio)
        db.refresh(author)
        db.refresh(club)
        assert audio.status == "cancelled"
        assert audio.storage_backend is None
        assert audio.storage_key is None
        assert audio.content_type is None
        assert audio.byte_size is None
        assert audio.moderation_status == "cancelled"
        assert "referenced cleanup" in audio.moderation_reason
        assert author.profile_photo_storage_key is None
        assert author.cover_photo_storage_key is None
        assert club.profile_photo_storage_key is None
        assert club.cover_photo_storage_key is None

        audit = db.query(models.AdminAuditLog).filter_by(action="storage_object_cleanup").one()
        assert audit.target_type == "storage_object"
        assert audit.reason == "referenced cleanup"
        assert audit.extra_data["key"] == shared_key
        assert audit.extra_data["cleanup"]["total"] == 5
    finally:
        db.close()
        models.Base.metadata.drop_all(engine)
        engine.dispose()


def test_admin_storage_cleanup_deletes_outside_prefix_object(monkeypatch):
    fake_client = FakeS3Client()
    set_s3_env(monkeypatch, fake_client)
    fake_client.objects = {
        "misc/outside.bin": {"Body": b"outside", "ContentType": "application/octet-stream"},
    }

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        admin_user = models.User(username="admin", email="admin@example.com", google_id="google-admin", is_admin=True)
        db.add(admin_user)
        db.commit()

        request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))
        response = admin_routes.cleanup_admin_storage_object(
            schemas.AdminStorageObjectCleanup(key="misc/outside.bin", reason="outside cleanup"),
            request,
            db=db,
            current_user=admin_user,
        )

        assert response == {
            "success": True,
            "key": "misc/outside.bin",
            "references_removed": 0,
            "references": [],
            "cleanup": {
                "counts": {
                    "audio": 0,
                    "user_profile_photo": 0,
                    "user_cover_photo": 0,
                    "club_profile_photo": 0,
                    "club_cover_photo": 0,
                },
                "total": 0,
            },
            "object": {
                "size": len(b"outside"),
                "content_type": "application/octet-stream",
                "etag": "etag-misc/outside.bin",
                "last_modified": datetime(2026, 5, 19, tzinfo=timezone.utc).isoformat(),
            },
        }
        assert "misc/outside.bin" not in fake_client.objects
        audit = db.query(models.AdminAuditLog).filter_by(action="storage_object_cleanup").one()
        assert audit.extra_data["prefix_type"] == "outside"
    finally:
        db.close()
        models.Base.metadata.drop_all(engine)
        engine.dispose()


def test_public_profile_media_redirects_to_signed_s3_url(monkeypatch):
    fake_client = FakeS3Client()
    set_s3_env(monkeypatch, fake_client)
    monkeypatch.setenv("PROFILE_MEDIA_SIGNED_URL_TTL_SECONDS", "456")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        user = models.User(
            username="author",
            email="author@example.com",
            google_id="google-author",
            premium_tier="trubadur",
            premium_until=utcnow_naive() + timedelta(days=30),
            profile_photo_storage_backend="s3",
            profile_photo_storage_key="users/1/profil.webp",
            profile_photo_content_type="image/webp",
        )
        db.add(user)
        db.commit()

        response = user_routes.get_public_profile_media("author", "profil", db=db)

        assert response.status_code == 307
        assert response.headers["location"] == (
            "https://signed.test/calimara/users/1/profil.webp?ttl=456"
        )
    finally:
        db.close()
        models.Base.metadata.drop_all(engine)
        engine.dispose()
