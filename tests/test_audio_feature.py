import os
import unittest
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

from app import audio_service, crud, models, statistics
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

    def post(self, owner: models.User, category: str = "poezie", slug: str = "poem") -> models.Post:
        post = models.Post(
            user_id=owner.id,
            title="Poem",
            slug=slug,
            content="<p>Text pentru citire.</p>",
            category=category,
            moderation_status="approved",
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def test_audio_access_requires_audio_tier(self):
        regular = self.user("regular", "trubadur")
        audio = self.user("audio", "cronicar")
        author_audio = self.user("authoraudio", "rapsod")

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

    def test_approved_post_does_not_auto_enqueue_tts(self):
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

        self.assertIsNone(audio)
        self.assertEqual(self.db.query(models.PostAudio).filter_by(post_id=post.id, source="tts").count(), 0)

    def test_post_audio_status_returns_url_without_audio_tier(self):
        owner = self.user("owner")
        listener = self.user("listener", "trubadur")
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
        self.assertTrue(payload["available"])
        self.assertTrue(payload["can_listen"])
        self.assertFalse(payload["requires_audio_tier"])
        self.assertEqual(payload["playback_url"], f"/api/audio/redare/{audio.id}")

    def test_post_audio_status_returns_local_stream_for_audio_tier(self):
        owner = self.user("owner")
        listener = self.user("listener", "cronicar")
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
        self.assertEqual(payload["playback_url"], f"/api/audio/redare/{audio.id}")

    def test_audio_quota_payload_for_audio_tier(self):
        owner = self.user("owner", "cronicar")
        payload = audio_service.audio_quota_payload(self.db, owner)
        self.assertTrue(payload["can_request"])
        self.assertEqual(payload["limit"], 100000)
        self.assertEqual(payload["used"], 0)
        self.assertEqual(payload["remaining"], 100000)

    def test_audio_quota_payload_for_author_audio_tier(self):
        owner = self.user("owner", "rapsod")
        payload = audio_service.audio_quota_payload(self.db, owner)
        self.assertTrue(payload["can_request"])
        self.assertEqual(payload["limit"], 250000)
        self.assertEqual(payload["remaining"], 250000)

    def test_audio_quota_ignores_failed_tts_rows(self):
        owner = self.user("owner", "cronicar")
        post = self.post(owner)
        period_start, period_end = crud.audio_tts_quota_period_for_user(owner)
        failed = crud.create_tts_audio_request(
            self.db,
            post_id=post.id,
            requester_user_id=owner.id,
            tts_character_count=1234,
            quota_period_start=period_start,
            quota_period_end=period_end,
        )
        crud.update_post_audio(self.db, failed.id, status="failed", error_message="provider failure")

        payload = audio_service.audio_quota_payload(self.db, owner)

        self.assertEqual(payload["used"], 0)
        self.assertEqual(payload["remaining"], 100000)

    def test_manual_tts_request_queues_and_counts_characters(self):
        owner = self.user("owner", "cronicar")
        post = self.post(owner)
        previous = os.environ.get("AUDIO_ENABLED")
        os.environ["AUDIO_ENABLED"] = "False"
        try:
            result = audio_service.request_tts_for_posts(self.db, owner, [post.id])
        finally:
            if previous is None:
                os.environ.pop("AUDIO_ENABLED", None)
            else:
                os.environ["AUDIO_ENABLED"] = previous

        self.assertEqual(len(result["queued"]), 1)
        audio = self.db.query(models.PostAudio).filter_by(post_id=post.id, source="tts").one()
        self.assertEqual(audio.requester_user_id, owner.id)
        self.assertEqual(audio.status, "pending")
        self.assertGreater(audio.tts_character_count, 0)
        self.assertEqual(result["quota"]["used"], audio.tts_character_count)

    def test_manual_tts_request_rejects_over_quota_without_creating_audio(self):
        owner = self.user("owner", "cronicar")
        post = models.Post(
            user_id=owner.id,
            title="Long",
            slug="long",
            content="x" * 100001,
            moderation_status="approved",
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)

        with self.assertRaises(audio_service.TTSQuotaExceeded):
            audio_service.request_tts_for_posts(self.db, owner, [post.id])

        self.assertEqual(self.db.query(models.PostAudio).filter_by(post_id=post.id, source="tts").count(), 0)

    def test_manual_tts_request_skips_existing_ready_audio_without_charge(self):
        owner = self.user("owner", "cronicar")
        post = self.post(owner)
        existing = crud.create_post_audio(
            self.db,
            post_id=post.id,
            source="tts",
            status="ready",
            storage_backend="local",
            storage_key="tts.mp3",
            content_type="audio/mpeg",
        )

        result = audio_service.request_tts_for_posts(self.db, owner, [post.id])

        self.assertEqual(result["queued"], [])
        self.assertEqual(result["skipped"][0]["audio_id"], existing.id)
        self.assertEqual(result["quota"]["used"], 0)
        self.assertEqual(self.db.query(models.PostAudio).filter_by(post_id=post.id, source="tts").count(), 1)

    def test_manual_tts_request_cancels_legacy_pending_and_queues_manual(self):
        owner = self.user("owner", "cronicar")
        post = self.post(owner)
        legacy = crud.create_post_audio(
            self.db,
            post_id=post.id,
            source="tts",
            status="pending",
        )

        result = audio_service.request_tts_for_posts(self.db, owner, [post.id])
        self.db.refresh(legacy)

        self.assertEqual(legacy.status, "cancelled")
        self.assertEqual(len(result["queued"]), 1)
        self.assertEqual(self.db.query(models.PostAudio).filter_by(post_id=post.id, source="tts").count(), 2)

    def test_manual_tts_request_retries_after_failed_audio_without_double_charging(self):
        owner = self.user("owner", "cronicar")
        post = self.post(owner)
        period_start, period_end = crud.audio_tts_quota_period_for_user(owner)
        failed = crud.create_tts_audio_request(
            self.db,
            post_id=post.id,
            requester_user_id=owner.id,
            tts_character_count=999,
            quota_period_start=period_start,
            quota_period_end=period_end,
        )
        crud.update_post_audio(self.db, failed.id, status="failed", error_message="provider failure")
        expected_count = audio_service.tts_character_count_for_post(post)

        previous = os.environ.get("AUDIO_ENABLED")
        os.environ["AUDIO_ENABLED"] = "False"
        try:
            result = audio_service.request_tts_for_posts(self.db, owner, [post.id])
        finally:
            if previous is None:
                os.environ.pop("AUDIO_ENABLED", None)
            else:
                os.environ["AUDIO_ENABLED"] = previous

        self.assertEqual(len(result["queued"]), 1)
        self.assertEqual(result["queued"][0]["character_count"], expected_count)
        self.assertEqual(result["quota"]["used"], expected_count)
        self.assertEqual(self.db.query(models.PostAudio).filter_by(post_id=post.id, source="tts").count(), 2)

    def test_random_listen_audio_requires_audio_tier(self):
        owner = self.user("owner")
        listener = self.user("listener", "trubadur")
        post = self.post(owner)
        crud.create_post_audio(
            self.db,
            post_id=post.id,
            source="tts",
            status="ready",
        )

        with self.assertRaises(audio_service.AudioListenForbidden):
            audio_service.random_listen_audio_track(self.db, listener, "poezie")

    def test_random_listen_audio_filters_by_mode(self):
        owner = self.user("owner")
        listener = self.user("listener", "cronicar")
        poem = self.post(owner, category="poezie", slug="poem-audio")
        story = self.post(owner, category="proza_scurta", slug="story-audio")
        crud.create_post_audio(self.db, post_id=poem.id, source="tts", status="ready")
        crud.create_post_audio(self.db, post_id=story.id, source="tts", status="ready")

        audio = audio_service.random_listen_audio_track(self.db, listener, "proza_scurta")

        self.assertEqual(audio.post.category, "proza_scurta")

    def test_record_listen_seconds_counts_author_and_post_once(self):
        owner = self.user("owner")
        listener = self.user("listener", "rapsod")
        post = self.post(owner)
        audio = crud.create_post_audio(self.db, post_id=post.id, source="tts", status="ready")

        first = audio_service.record_listen_seconds(
            self.db,
            listener,
            event_id="listen-event-1",
            audio_id=audio.id,
            seconds=12,
            mode="poezie",
        )
        second = audio_service.record_listen_seconds(
            self.db,
            listener,
            event_id="listen-event-1",
            audio_id=audio.id,
            seconds=12,
            mode="poezie",
        )

        self.db.refresh(owner)
        self.db.refresh(post)
        self.assertTrue(first["recorded"])
        self.assertFalse(second["recorded"])
        self.assertEqual(post.seconds_listened, 12)
        self.assertEqual(owner.seconds_listened, 12)
        self.assertEqual(self.db.query(models.AudioListenEvent).count(), 1)

    def test_record_listen_seconds_rejects_wrong_mode(self):
        owner = self.user("owner")
        listener = self.user("listener", "cronicar")
        post = self.post(owner, category="poezie")
        audio = crud.create_post_audio(self.db, post_id=post.id, source="tts", status="ready")

        with self.assertRaises(audio_service.AudioListenInvalid):
            audio_service.record_listen_seconds(
                self.db,
                listener,
                event_id="listen-event-2",
                audio_id=audio.id,
                seconds=5,
                mode="proza_scurta",
            )

    def test_listen_stats_include_seconds(self):
        owner = self.user("owner")
        listener = self.user("listener", "cronicar")
        post = self.post(owner)
        audio = crud.create_post_audio(self.db, post_id=post.id, source="tts", status="ready")
        audio_service.record_listen_seconds(
            self.db,
            listener,
            event_id="listen-event-3",
            audio_id=audio.id,
            seconds=21,
            mode="poezie",
        )

        post_stats = statistics.get_post_stats(self.db, post.id)
        author_stats = statistics.get_author_stats(self.db, owner.id)
        my_stats = statistics.get_my_stats(self.db, owner.id)

        self.assertEqual(post_stats["seconds_listened"], 21)
        self.assertEqual(author_stats["seconds_listened"], 21)
        self.assertEqual(my_stats["seconds_listened"], 21)
        self.assertEqual(my_stats["posts_detail"][0]["seconds_listened"], 21)


if __name__ == "__main__":
    unittest.main()
