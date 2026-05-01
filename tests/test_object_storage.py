from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import audio_storage, models, object_storage, profile_media
from app.routers import user_routes
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
            premium_tier="premium",
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
