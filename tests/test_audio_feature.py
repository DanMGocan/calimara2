import inspect
import os
import unittest
from datetime import timedelta
from unittest.mock import patch

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

    def test_post_audio_status_exposes_author_upload_state_for_rapsod_owner(self):
        owner = self.user("owner", "rapsod")
        post = self.post(owner)
        author = crud.create_post_audio(
            self.db,
            post_id=post.id,
            requester_user_id=owner.id,
            source="author",
            status="pending",
            storage_backend="local",
            storage_key="author.webm",
            content_type="audio/webm",
        )

        payload = audio_service.post_audio_status_payload(self.db, post.id, owner)

        self.assertFalse(payload["available"])
        self.assertTrue(payload["author_audio_can_upload"])
        self.assertEqual(payload["author_audio_status"], author.status)
        self.assertIn("transcriere", payload["author_audio_message"])

    def test_post_audio_status_hides_author_upload_from_lower_tier(self):
        owner = self.user("owner", "cronicar")
        post = self.post(owner)

        payload = audio_service.post_audio_status_payload(self.db, post.id, owner)

        self.assertFalse(payload["author_audio_can_upload"])
        self.assertEqual(payload["author_audio_status"], "missing")

    def test_audio_quota_payload_for_audio_tier(self):
        owner = self.user("owner", "cronicar")
        payload = audio_service.audio_quota_payload(self.db, owner)
        self.assertTrue(payload["can_request"])
        self.assertEqual(payload["limit"], 100000)
        self.assertEqual(payload["used"], 0)
        self.assertEqual(payload["remaining"], 100000)

    def test_audio_quota_payload_for_free_and_trubadur_tiers(self):
        free = self.user("free")
        trubadur = self.user("trubadur", "trubadur")

        free_payload = audio_service.audio_quota_payload(self.db, free)
        trubadur_payload = audio_service.audio_quota_payload(self.db, trubadur)

        self.assertTrue(free_payload["can_request"])
        self.assertEqual(free_payload["premium_tier"], "free")
        self.assertEqual(free_payload["limit"], 1000)
        self.assertEqual(free_payload["remaining"], 1000)
        self.assertIsNotNone(free_payload["period_start"])
        self.assertIsNotNone(free_payload["period_end"])
        self.assertFalse(trubadur.has_audio_access)
        self.assertTrue(trubadur_payload["can_request"])
        self.assertEqual(trubadur_payload["premium_tier"], "trubadur")
        self.assertEqual(trubadur_payload["limit"], 50000)
        self.assertEqual(trubadur_payload["remaining"], 50000)

    def test_audio_quota_payload_for_author_audio_tier(self):
        owner = self.user("owner", "rapsod")
        payload = audio_service.audio_quota_payload(self.db, owner)
        self.assertTrue(payload["can_request"])
        self.assertEqual(payload["limit"], 200000)
        self.assertEqual(payload["remaining"], 200000)

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

    def test_free_user_can_queue_tts_within_starter_quota(self):
        owner = self.user("freeaudio")
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
        self.assertEqual(result["quota"]["limit"], 1000)
        self.assertLessEqual(result["quota"]["used"], 1000)
        audio = self.db.query(models.PostAudio).filter_by(post_id=post.id, source="tts").one()
        self.assertEqual(audio.requester_user_id, owner.id)
        self.assertEqual(audio.status, "pending")

    def test_free_user_tts_request_rejects_over_starter_quota(self):
        owner = self.user("freequota")
        post = models.Post(
            user_id=owner.id,
            title="Long",
            slug="free-long",
            content="x" * 1001,
            moderation_status="approved",
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)

        with self.assertRaises(audio_service.TTSQuotaExceeded):
            audio_service.request_tts_for_posts(self.db, owner, [post.id])

        self.assertEqual(self.db.query(models.PostAudio).filter_by(post_id=post.id, source="tts").count(), 0)

    def test_tts_split_keeps_long_romanian_text_under_configured_byte_limit(self):
        sentence = "În curtea imensă a domnului Iorgu, băiatul se întoarse acasă cu pași rari și cuvinte apăsate."
        text = "\n\n".join([sentence.replace(" ", "\u00a0") for _ in range(140)])

        with patch.dict(os.environ, {"GOOGLE_TTS_MAX_BYTES": "3200"}):
            chunks = audio_service.split_text_for_tts(text)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk.encode("utf-8")) <= 3200 for chunk in chunks))

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

    def test_manual_tts_request_skips_failed_audio_with_active_retry_job(self):
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
        self.db.add(
            models.AIJob(
                job_type="tts_audio_generation",
                target_type="audio",
                target_id=failed.id,
                status="pending",
                max_attempts=3,
            )
        )
        self.db.commit()

        result = audio_service.request_tts_for_posts(self.db, owner, [post.id])

        self.assertEqual(result["queued"], [])
        self.assertEqual(result["skipped"][0]["audio_id"], failed.id)
        self.assertEqual(result["skipped"][0]["status"], "pending")
        self.assertEqual(self.db.query(models.PostAudio).filter_by(post_id=post.id, source="tts").count(), 1)

    def test_author_recording_upload_sets_requester_and_cancels_old_non_ready_attempts(self):
        owner = self.user("owner", "rapsod")
        post = self.post(owner)
        ready = crud.create_post_audio(
            self.db,
            post_id=post.id,
            requester_user_id=owner.id,
            source="author",
            status="ready",
            storage_backend="local",
            storage_key="author-ready.mp3",
            content_type="audio/mpeg",
        )
        pending = crud.create_post_audio(
            self.db,
            post_id=post.id,
            requester_user_id=owner.id,
            source="author",
            status="pending",
        )
        flagged = crud.create_post_audio(
            self.db,
            post_id=post.id,
            requester_user_id=owner.id,
            source="author",
            status="flagged",
        )

        with patch.object(audio_service.audio_storage, "save_audio_bytes", return_value=("local", "new.webm", 9)), \
             patch("app.ai_queue.enqueue_author_audio_moderation_job") as enqueue:
            uploaded = audio_service.create_author_recording(
                self.db,
                post,
                b"new audio",
                "audio/webm",
                requester_user_id=owner.id,
            )

        self.db.refresh(ready)
        self.db.refresh(pending)
        self.db.refresh(flagged)
        self.assertEqual(uploaded.status, "pending")
        self.assertEqual(uploaded.requester_user_id, owner.id)
        self.assertEqual(pending.status, "cancelled")
        self.assertEqual(flagged.status, "cancelled")
        self.assertEqual(ready.status, "ready")
        self.assertEqual(crud.get_best_audio_for_post(self.db, post.id).id, ready.id)
        enqueue.assert_called_once()

    def test_author_recording_processing_marks_matching_clean_audio_ready(self):
        owner = self.user("owner", "rapsod")
        post = self.post(owner)
        audio = crud.create_post_audio(
            self.db,
            post_id=post.id,
            requester_user_id=owner.id,
            source="author",
            status="pending",
            storage_backend="local",
            storage_key="author.webm",
            content_type="audio/webm",
        )
        result = audio_service.moderation.ModerationResult(
            audio_service.moderation.ModerationStatus.APPROVED,
            0.0,
            "clean",
        )

        with patch.object(audio_service.audio_storage, "load_audio_bytes", return_value=b"audio"), \
             patch.object(audio_service, "transcribe_audio", return_value=("Text pentru citire.", 0.94)), \
             patch.object(audio_service.moderation, "moderate_comment", return_value=result), \
             patch.object(audio_service.moderation, "log_moderation_decision"):
            processed = audio_service.process_author_recording(self.db, audio)

        self.assertEqual(processed.status, "ready")
        self.assertEqual(processed.moderation_status, "approved")
        self.assertGreaterEqual(processed.transcript_match_score, 0.25)

    def test_author_recording_processing_flags_mismatched_audio(self):
        owner = self.user("owner", "rapsod")
        post = self.post(owner)
        audio = crud.create_post_audio(
            self.db,
            post_id=post.id,
            requester_user_id=owner.id,
            source="author",
            status="pending",
            storage_backend="local",
            storage_key="author.webm",
            content_type="audio/webm",
        )
        result = audio_service.moderation.ModerationResult(
            audio_service.moderation.ModerationStatus.APPROVED,
            0.0,
            "clean",
        )

        with patch.object(audio_service.audio_storage, "load_audio_bytes", return_value=b"audio"), \
             patch.object(audio_service, "transcribe_audio", return_value=("Altă poveste fără legătură.", 0.88)), \
             patch.object(audio_service.moderation, "moderate_comment", return_value=result), \
             patch.object(audio_service.moderation, "log_moderation_decision"):
            processed = audio_service.process_author_recording(self.db, audio)

        self.assertEqual(processed.status, "flagged")
        self.assertEqual(processed.moderation_status, "flagged")
        self.assertIn("Transcript", processed.moderation_reason)

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

    def test_audio_track_payload_includes_viewer_author_relationships(self):
        owner = self.user("owner")
        listener = self.user("listener", "cronicar")
        post = self.post(owner, category="poezie", slug="poem-audio")
        audio = crud.create_post_audio(self.db, post_id=post.id, source="tts", status="ready")
        self.db.add(models.UserFollow(follower_id=listener.id, followed_id=owner.id))
        user1_id, user2_id = sorted([owner.id, listener.id])
        self.db.add(
            models.Friendship(
                user1_id=user1_id,
                user2_id=user2_id,
                requested_by_id=owner.id,
                status="pending",
            )
        )
        self.db.commit()

        payload = audio_service.audio_track_payload(audio, current_user=listener, db=self.db)

        self.assertEqual(payload["author_id"], owner.id)
        self.assertEqual(payload["author_username"], owner.username)
        self.assertTrue(payload["viewer_following"])
        self.assertEqual(payload["viewer_friendship_status"], "incoming_pending")
        self.assertIsNotNone(payload["viewer_friendship_id"])

    def test_author_scoped_random_playback_requires_audio_tier_and_author_ready_audio(self):
        author = self.user("author")
        other_author = self.user("otherauthor")
        listener = self.user("listener", "cronicar")
        lower_tier = self.user("lowertier", "trubadur")
        poem = self.post(author, category="poezie", slug="author-poem")
        story = self.post(author, category="proza_scurta", slug="author-story")
        other_post = self.post(other_author, category="proza_scurta", slug="other-story")
        crud.create_post_audio(self.db, post_id=poem.id, source="tts", status="ready")
        crud.create_post_audio(self.db, post_id=story.id, source="tts", status="ready")
        crud.create_post_audio(self.db, post_id=other_post.id, source="tts", status="ready")

        with self.assertRaises(audio_service.AudioListenForbidden):
            audio_service.random_author_listen_audio_track(self.db, lower_tier, author.username, "toate")

        audio = audio_service.random_author_listen_audio_track(self.db, listener, author.username, "proza_scurta")

        self.assertEqual(audio.post_id, story.id)
        self.assertEqual(audio.post.user_id, author.id)

    def test_author_random_audio_query_avoids_postgres_distinct_random(self):
        source = inspect.getsource(crud.get_random_ready_audio_for_author_listen_mode)

        self.assertIn(".exists()", source)
        self.assertIn(".order_by(func.random()).limit(1)", source)
        self.assertNotIn(".distinct().order_by(func.random())", source)

    def test_audio_playlist_crud_is_owner_scoped(self):
        owner = self.user("owner", "rapsod")
        other = self.user("other", "rapsod")

        playlist = crud.create_audio_playlist(self.db, owner.id, "  Favorite audio  ")
        updated = crud.update_audio_playlist(self.db, playlist, title="  Seara  ")

        self.assertEqual(updated.title, "Seara")
        self.assertEqual(crud.list_audio_playlists(self.db, owner.id)[0].id, playlist.id)
        self.assertIsNone(crud.get_audio_playlist_for_owner(self.db, playlist.id, other.id))
        self.assertIsNotNone(crud.get_audio_playlist_for_owner(self.db, playlist.id, owner.id))

    def test_audio_playlist_add_requires_ready_audio_and_rejects_duplicates(self):
        owner = self.user("owner", "rapsod")
        playlist = crud.create_audio_playlist(self.db, owner.id, "Lista mea")
        ready_post = self.post(owner, slug="ready")
        missing_audio_post = self.post(owner, slug="missing")
        pending_post = self.post(owner, slug="pending")
        pending_post.moderation_status = "pending"
        self.db.commit()
        crud.create_post_audio(self.db, post_id=ready_post.id, source="tts", status="ready")
        crud.create_post_audio(self.db, post_id=missing_audio_post.id, source="tts", status="pending")

        missing_item, missing_error = crud.add_post_to_audio_playlist(self.db, playlist, missing_audio_post)
        pending_item, pending_error = crud.add_post_to_audio_playlist(self.db, playlist, pending_post)
        item, error = crud.add_post_to_audio_playlist(self.db, playlist, ready_post)
        duplicate, duplicate_error = crud.add_post_to_audio_playlist(self.db, playlist, ready_post)

        self.assertIsNone(missing_item)
        self.assertEqual(missing_error, "audio_missing")
        self.assertIsNone(pending_item)
        self.assertEqual(pending_error, "post_unavailable")
        self.assertIsNone(error)
        self.assertEqual(item.position, 1)
        self.assertEqual(duplicate.id, item.id)
        self.assertEqual(duplicate_error, "already_added")

    def test_audio_playlist_remove_delete_and_ordered_playback(self):
        owner = self.user("owner", "rapsod")
        playlist = crud.create_audio_playlist(self.db, owner.id, "Ordine")
        posts = [self.post(owner, slug=f"audio-{index}") for index in range(1, 4)]
        for post in posts:
            crud.create_post_audio(self.db, post_id=post.id, source="tts", status="ready")
            item, error = crud.add_post_to_audio_playlist(self.db, playlist, post)
            self.assertIsNone(error)
            self.assertIsNotNone(item)

        payload = audio_service.audio_playlist_playback_payload(self.db, playlist, current_user=owner)
        self.assertEqual([track["post_id"] for track in payload["tracks"]], [post.id for post in posts])

        self.assertTrue(crud.remove_post_from_audio_playlist(self.db, playlist, posts[1].id))
        items = crud.get_audio_playlist_items(self.db, playlist.id)
        self.assertEqual([item.post_id for item in items], [posts[0].id, posts[2].id])
        self.assertEqual([item.position for item in items], [1, 2])

        self.db.delete(posts[0])
        self.db.commit()
        remaining_items = crud.get_audio_playlist_items(self.db, playlist.id)
        self.assertEqual([item.post_id for item in remaining_items], [posts[2].id])

        crud.delete_audio_playlist(self.db, playlist)
        self.assertEqual(self.db.query(models.AudioPlaylistItem).count(), 0)
        self.assertEqual(self.db.query(models.AudioPlaylist).count(), 0)

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

    def test_record_listen_seconds_allows_public_post_listener_without_audio_tier(self):
        owner = self.user("owner")
        listener = self.user("listener")
        post = self.post(owner)
        audio = crud.create_post_audio(self.db, post_id=post.id, source="tts", status="ready")

        result = audio_service.record_listen_seconds(
            self.db,
            listener,
            event_id="listen-event-free-user",
            audio_id=audio.id,
            seconds=9,
            mode="toate",
        )

        event = self.db.query(models.AudioListenEvent).filter_by(event_id="listen-event-free-user").one()
        self.db.refresh(owner)
        self.db.refresh(post)
        self.assertTrue(result["recorded"])
        self.assertEqual(event.listener_user_id, listener.id)
        self.assertEqual(post.seconds_listened, 9)
        self.assertEqual(owner.seconds_listened, 9)

    def test_record_listen_seconds_allows_anonymous_public_post_listener(self):
        owner = self.user("owner")
        post = self.post(owner)
        audio = crud.create_post_audio(self.db, post_id=post.id, source="tts", status="ready")

        result = audio_service.record_listen_seconds(
            self.db,
            None,
            event_id="listen-event-anonymous",
            audio_id=audio.id,
            seconds=7,
            mode="toate",
        )

        event = self.db.query(models.AudioListenEvent).filter_by(event_id="listen-event-anonymous").one()
        self.db.refresh(owner)
        self.db.refresh(post)
        self.assertTrue(result["recorded"])
        self.assertIsNone(event.listener_user_id)
        self.assertEqual(post.seconds_listened, 7)
        self.assertEqual(owner.seconds_listened, 7)

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
