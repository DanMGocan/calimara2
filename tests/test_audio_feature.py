import os
import unittest
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

from app import audio_service, crud, models
from app.week_util import utcnow_naive


class AudioFeatureTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def user(self, name: str, tier: str = "free") -> models.User:
        user = models.User(
            username=name,
            email=f"{name}@example.com",
            google_id=f"google-{name}",
            premium_tier=tier,
        )
        if tier != "free":
            user.premium_until = utcnow_naive() + timedelta(days=30)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def post(self, owner: models.User) -> models.Post:
        post = models.Post(
            user_id=owner.id,
            title="Poem",
            slug="poem",
            content="<p>Text pentru citire.</p>",
            moderation_status="approved",
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def test_audio_access_requires_audio_tier(self):
        regular = self.user("regular", "premium")
        audio = self.user("audio", "audio")
        author_audio = self.user("authoraudio", "author_audio")

        self.assertTrue(regular.is_premium)
        self.assertFalse(regular.has_audio_access)
        self.assertFalse(regular.has_author_audio_access)
        self.assertTrue(audio.is_premium)
        self.assertTrue(audio.has_audio_access)
        self.assertFalse(audio.has_author_audio_access)
        self.assertTrue(author_audio.is_premium)
        self.assertTrue(author_audio.has_audio_access)
        self.assertTrue(author_audio.has_author_audio_access)

    def test_best_audio_prefers_author_recording(self):
        owner = self.user("owner")
        post = self.post(owner)
        tts = crud.create_post_audio(
            self.db,
            post_id=post.id,
            source="tts",
            status="ready",
            storage_backend="local",
            storage_key="tts.mp3",
            content_type="audio/mpeg",
        )
        author = crud.create_post_audio(
            self.db,
            post_id=post.id,
            source="author",
            status="ready",
            storage_backend="local",
            storage_key="author.mp3",
            content_type="audio/mpeg",
        )

        best = crud.get_best_audio_for_post(self.db, post.id)
        self.assertEqual(best.id, author.id)
        self.assertNotEqual(best.id, tts.id)

    def test_approved_post_enqueues_tts_even_when_generation_disabled(self):
        owner = self.user("owner")
        post = self.post(owner)
        previous = os.environ.get("AUDIO_ENABLED")
        os.environ["AUDIO_ENABLED"] = "False"
        try:
            audio = audio_service.enqueue_tts_for_post(self.db, post)
        finally:
            if previous is None:
                os.environ.pop("AUDIO_ENABLED", None)
            else:
                os.environ["AUDIO_ENABLED"] = previous

        self.assertIsNotNone(audio)
        self.assertEqual(audio.source, "tts")
        self.assertEqual(audio.status, "pending")

    def test_post_audio_status_hides_url_without_audio_tier(self):
        owner = self.user("owner")
        listener = self.user("listener", "premium")
        post = self.post(owner)
        crud.create_post_audio(
            self.db,
            post_id=post.id,
            source="tts",
            status="ready",
            storage_backend="local",
            storage_key="tts.mp3",
            content_type="audio/mpeg",
        )

        payload = audio_service.post_audio_status_payload(self.db, post.id, listener)
        self.assertTrue(payload["available"])
        self.assertFalse(payload["can_listen"])
        self.assertIsNone(payload["playback_url"])

    def test_post_audio_status_returns_local_stream_for_audio_tier(self):
        owner = self.user("owner")
        listener = self.user("listener", "audio")
        post = self.post(owner)
        audio = crud.create_post_audio(
            self.db,
            post_id=post.id,
            source="tts",
            status="ready",
            storage_backend="local",
            storage_key="tts.mp3",
            content_type="audio/mpeg",
        )

        payload = audio_service.post_audio_status_payload(self.db, post.id, listener)
        self.assertTrue(payload["can_listen"])
        self.assertEqual(payload["playback_url"], f"/api/audio/stream/{audio.id}")


if __name__ == "__main__":
    unittest.main()
