import os
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

from app import ai_queue, crud, models, moderation, schemas
from app.week_util import utcnow_naive


class AIQueueTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def make_user(self, username: str = "writer") -> models.User:
        user = models.User(
            username=username,
            email=f"{username}@example.com",
            google_id=f"google-{username}",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def test_ai_jobs_can_be_claimed_retried_and_completed(self):
        job = crud.enqueue_ai_job(
            self.db,
            job_type="example",
            target_type="post",
            target_id=123,
            max_attempts=2,
        )

        claimed = crud.claim_pending_ai_jobs(self.db, limit=5, worker_id="worker-1")
        self.assertEqual([item.id for item in claimed], [job.id])
        self.assertEqual(claimed[0].status, "processing")
        self.assertEqual(claimed[0].attempts, 1)

        retried = crud.fail_ai_job(self.db, claimed[0], "temporary failure", retry=True)
        self.assertEqual(retried.status, "pending")
        self.assertEqual(retried.error_message, "temporary failure")

        retried.run_after = retried.created_at
        self.db.commit()
        claimed_again = crud.claim_pending_ai_jobs(self.db, limit=5, worker_id="worker-2")
        self.assertEqual([item.id for item in claimed_again], [job.id])
        completed = crud.complete_ai_job(self.db, claimed_again[0])
        self.assertEqual(completed.status, "completed")

    def test_post_publish_job_approves_post_and_enqueues_followups(self):
        user = self.make_user()
        follower = self.make_user("postfollower")
        post = crud.create_user_post(
            self.db,
            schemas.PostCreate(title="Poem", content="Un text pentru coadă.", category="proza_scurta", ai_critic=True),
            user_id=user.id,
        )
        crud.create_follow(self.db, follower.id, user.id)
        self.db.commit()
        ai_queue.enqueue_post_publish_job(self.db, post, ai_critic_requested=True)
        approved = SimpleNamespace(
            status=moderation.ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason="ok",
        )

        with patch.dict(os.environ, {"AUDIO_ENABLED": "True"}), patch.object(
            ai_queue.moderation, "moderate_post_with_logging", return_value=approved
        ):
            processed = ai_queue.process_ai_jobs(self.db, limit=1, worker="test-worker")

        self.assertEqual(processed, 1)
        self.db.refresh(post)
        self.assertEqual(post.moderation_status, "approved")
        self.assertEqual(post.category, "proza_scurta")
        self.assertTrue(post.ai_critic_requested)
        self.assertEqual(self.db.query(models.PostAudio).filter_by(post_id=post.id, source="tts").count(), 0)
        queued_types = {
            job.job_type
            for job in self.db.query(models.AIJob).filter(models.AIJob.status == "pending").all()
        }
        self.assertIn(ai_queue.JOB_AI_CRITIC, queued_types)
        self.assertNotIn(ai_queue.JOB_TTS_AUDIO, queued_types)
        self.assertEqual(self.db.query(models.GologaniTransaction).filter_by(source_type="post").count(), 1)
        follower_notification = self.db.query(models.Notification).filter_by(
            user_id=follower.id,
            type="followed_user_new_post",
        ).one()
        self.assertEqual(follower_notification.link, f"//{user.username}.calimara.ro/{post.slug}")
        self.assertEqual(follower_notification.extra_data["post_id"], post.id)

    def test_imported_post_publish_job_approves_without_rewards_or_follower_notifications(self):
        user = self.make_user()
        follower = self.make_user("importfollower")
        post = crud.create_user_post(
            self.db,
            schemas.PostCreate(title="Arhivă", content="Un text importat.", category="poezie", ai_critic=False),
            user_id=user.id,
        )
        crud.create_follow(self.db, follower.id, user.id)
        self.db.add(ai_queue.build_imported_post_publish_job(post))
        self.db.commit()
        approved = SimpleNamespace(
            status=moderation.ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason="ok",
        )

        with patch.object(ai_queue.moderation, "moderate_post_with_logging", return_value=approved) as moderate:
            processed = ai_queue.process_ai_jobs(self.db, limit=1, worker="test-worker")

        self.assertEqual(processed, 1)
        moderate.assert_called_once()
        self.db.refresh(post)
        self.assertEqual(post.moderation_status, "approved")
        self.assertEqual(self.db.query(models.GologaniTransaction).filter_by(source_type="post").count(), 0)
        self.assertEqual(
            self.db.query(models.Notification).filter_by(user_id=follower.id, type="followed_user_new_post").count(),
            0,
        )

    def test_tts_generation_failure_keeps_ai_job_retryable(self):
        user = self.make_user()
        post = crud.create_user_post(
            self.db,
            schemas.PostCreate(title="Poem", content="Un text pentru audio.", category="poezie", ai_critic=False),
            user_id=user.id,
        )
        post.moderation_status = "approved"
        self.db.commit()
        self.db.refresh(post)
        audio = crud.create_post_audio(
            self.db,
            post_id=post.id,
            requester_user_id=user.id,
            source="tts",
            status="pending",
            tts_character_count=25,
        )
        job = ai_queue.enqueue_tts_audio_job(self.db, audio)

        with patch.object(ai_queue.audio_service, "synthesize_text", side_effect=RuntimeError("provider down")):
            processed = ai_queue.process_ai_jobs(self.db, limit=1, worker="test-worker")

        self.assertEqual(processed, 1)
        self.db.refresh(audio)
        job = self.db.query(models.AIJob).filter(models.AIJob.id == job.id).one()
        self.assertEqual(audio.status, "pending")
        self.assertEqual(audio.error_message, "provider down")
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.attempts, 1)
        self.assertIn("provider down", job.error_message)
        payload = ai_queue.audio_service.post_audio_status_payload(self.db, post.id, user)
        self.assertEqual(payload["status"], "pending")
        self.assertEqual(payload["message"], "Generarea audio se reîncearcă.")

    def test_tts_generation_second_failure_waits_before_third_attempt(self):
        user = self.make_user()
        post = crud.create_user_post(
            self.db,
            schemas.PostCreate(title="Poem", content="Un text pentru audio.", category="poezie", ai_critic=False),
            user_id=user.id,
        )
        post.moderation_status = "approved"
        self.db.commit()
        self.db.refresh(post)
        audio = crud.create_post_audio(
            self.db,
            post_id=post.id,
            requester_user_id=user.id,
            source="tts",
            status="pending",
            tts_character_count=25,
        )
        job = ai_queue.enqueue_tts_audio_job(self.db, audio)
        self.assertEqual(job.max_attempts, 3)

        with patch.dict(os.environ, {"TTS_THIRD_ATTEMPT_DELAY_SECONDS": "900"}), patch.object(
            ai_queue.audio_service, "synthesize_text", side_effect=RuntimeError("provider down")
        ):
            ai_queue.process_ai_jobs(self.db, limit=1, worker="test-worker")
            job = self.db.query(models.AIJob).filter(models.AIJob.id == job.id).one()
            job.run_after = job.created_at
            self.db.commit()

            before_retry = utcnow_naive()
            ai_queue.process_ai_jobs(self.db, limit=1, worker="test-worker")

        job = self.db.query(models.AIJob).filter(models.AIJob.id == job.id).one()
        self.db.refresh(audio)
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.attempts, 2)
        self.assertEqual(audio.status, "pending")
        self.assertGreaterEqual(job.run_after, before_retry + timedelta(seconds=890))
        self.assertLessEqual(job.run_after, utcnow_naive() + timedelta(seconds=910))

    def test_tts_generation_final_failure_marks_audio_failed(self):
        user = self.make_user()
        post = crud.create_user_post(
            self.db,
            schemas.PostCreate(title="Poem", content="Un text pentru audio.", category="poezie", ai_critic=False),
            user_id=user.id,
        )
        post.moderation_status = "approved"
        self.db.commit()
        self.db.refresh(post)
        audio = crud.create_post_audio(
            self.db,
            post_id=post.id,
            requester_user_id=user.id,
            source="tts",
            status="pending",
            tts_character_count=25,
        )
        job = crud.enqueue_ai_job(
            self.db,
            job_type=ai_queue.JOB_TTS_AUDIO,
            target_type="audio",
            target_id=audio.id,
            max_attempts=1,
        )

        with patch.object(ai_queue.audio_service, "synthesize_text", side_effect=RuntimeError("provider down")):
            processed = ai_queue.process_ai_jobs(self.db, limit=1, worker="test-worker")

        self.assertEqual(processed, 1)
        self.db.refresh(audio)
        job = self.db.query(models.AIJob).filter(models.AIJob.id == job.id).one()
        self.assertEqual(audio.status, "failed")
        self.assertEqual(audio.error_message, "provider down")
        self.assertEqual(job.status, "failed")
        payload = ai_queue.audio_service.post_audio_status_payload(self.db, post.id, user)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["message"], "Generarea audio a eșuat.")

    def test_cancelled_author_audio_job_is_skipped(self):
        user = self.make_user()
        post = crud.create_user_post(
            self.db,
            schemas.PostCreate(title="Poem", content="Un text pentru audio.", category="poezie", ai_critic=False),
            user_id=user.id,
        )
        post.moderation_status = "approved"
        self.db.commit()
        self.db.refresh(post)
        audio = crud.create_post_audio(
            self.db,
            post_id=post.id,
            requester_user_id=user.id,
            source="author",
            status="cancelled",
        )
        job = ai_queue.enqueue_author_audio_moderation_job(self.db, audio)

        with patch.object(ai_queue.audio_service, "process_author_recording") as process_author:
            processed = ai_queue.process_ai_jobs(self.db, limit=1, worker="test-worker")

        job = self.db.query(models.AIJob).filter(models.AIJob.id == job.id).one()
        self.assertEqual(processed, 1)
        self.assertEqual(job.status, "completed")
        process_author.assert_not_called()

    def test_failed_flush_rolls_job_back_to_retry_without_sticking_processing(self):
        job = crud.enqueue_ai_job(
            self.db,
            job_type="broken_flush",
            target_type="post",
            target_id=123,
            max_attempts=2,
        )

        def broken_flush(db, claimed_job):
            db.add(
                models.User(
                    username="duplicate",
                    email="duplicate@example.com",
                    google_id="duplicate-google",
                )
            )
            db.flush()
            db.add(
                models.User(
                    username="duplicate",
                    email="other@example.com",
                    google_id="other-google",
                )
            )
            db.flush()

        claimed = crud.claim_pending_ai_jobs(self.db, limit=1, worker_id="test-worker")
        self.assertEqual([item.id for item in claimed], [job.id])

        with patch.dict(ai_queue._HANDLERS, {"broken_flush": broken_flush}):
            ai_queue.process_claimed_job(self.db, claimed[0])

        refreshed = self.db.query(models.AIJob).filter(models.AIJob.id == job.id).one()
        self.assertEqual(refreshed.status, "pending")
        self.assertEqual(refreshed.attempts, 1)
        self.assertIsNone(refreshed.locked_at)
        self.assertIsNone(refreshed.locked_by)
        self.assertIn("UNIQUE", refreshed.error_message.upper())

    def test_comment_moderation_job_updates_comment_without_blocking_create(self):
        user = self.make_user()
        target = self.make_user("target")
        post = crud.create_user_post(
            self.db,
            schemas.PostCreate(title="Text", content="Conținut", category="proza_scurta", ai_critic=False),
            user_id=user.id,
        )
        post.moderation_status = "approved"
        self.db.commit()
        comment = crud.create_comment(
            self.db,
            schemas.CommentCreate(content="Comentariu curat pentru @target"),
            post_id=post.id,
            user_id=user.id,
        )
        ai_queue.enqueue_comment_moderation_job(self.db, comment)
        approved = SimpleNamespace(
            status=moderation.ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason="ok",
        )

        with patch.object(ai_queue.moderation, "moderate_comment_with_logging", return_value=approved):
            ai_queue.process_ai_jobs(self.db, limit=1, worker="test-worker")

        self.db.refresh(comment)
        self.assertTrue(comment.approved)
        self.assertEqual(comment.moderation_status, "approved")
        self.assertEqual(self.db.query(models.GologaniTransaction).filter_by(source_type="comment").count(), 1)
        self.assertEqual(crud.get_unread_notification_count(self.db, target.id), 1)

    def test_flagged_comment_notification_uses_author_post_link(self):
        author = self.make_user("commentauthor")
        commenter = self.make_user("commenter")
        post = crud.create_user_post(
            self.db,
            schemas.PostCreate(title="Text", content="Conținut", category="proza_scurta", ai_critic=False),
            user_id=author.id,
        )
        post.moderation_status = "approved"
        self.db.commit()
        comment = crud.create_comment(
            self.db,
            schemas.CommentCreate(content="Comentariu problematic"),
            post_id=post.id,
            user_id=commenter.id,
        )
        ai_queue.enqueue_comment_moderation_job(self.db, comment)
        flagged = SimpleNamespace(
            status=moderation.ModerationStatus.FLAGGED,
            toxicity_score=0.9,
            reason="manual",
        )

        with patch.object(ai_queue.moderation, "moderate_comment_with_logging", return_value=flagged):
            ai_queue.process_ai_jobs(self.db, limit=1, worker="test-worker")

        notification = self.db.query(models.Notification).filter_by(
            user_id=commenter.id,
            type="moderation_queue",
        ).one()
        self.assertEqual(notification.link, f"//{author.username}.calimara.ro/{post.slug}")

    def test_final_moderation_failures_are_flagged_not_auto_approved(self):
        user = self.make_user()
        post = crud.create_user_post(
            self.db,
            schemas.PostCreate(title="Poem", content="Text de verificat.", category="poezie", ai_critic=True),
            user_id=user.id,
        )
        approved_post = crud.create_user_post(
            self.db,
            schemas.PostCreate(title="Public", content="Text public.", category="proza_scurta", ai_critic=False),
            user_id=user.id,
        )
        approved_post.moderation_status = "approved"
        self.db.commit()
        comment = crud.create_comment(
            self.db,
            schemas.CommentCreate(content="Comentariu de verificat"),
            post_id=approved_post.id,
            user_id=user.id,
        )
        thread = crud.create_forum_thread(
            self.db,
            user,
            schemas.ForumThreadCreate(
                section="general",
                title="Discuție",
                content="Text de verificat",
            ),
        )
        reply_thread = crud.create_forum_thread(
            self.db,
            user,
            schemas.ForumThreadCreate(
                section="general",
                title="Discuție publică",
                content="Text public",
            ),
        )
        reply_thread.moderation_status = "approved"
        self.db.commit()
        reply, error = crud.create_forum_reply(
            self.db,
            user,
            reply_thread,
            schemas.ForumReplyCreate(content="Răspuns de verificat"),
        )
        self.assertIsNone(error)

        jobs = [
            ai_queue.enqueue_post_publish_job(self.db, post, ai_critic_requested=True),
            ai_queue.enqueue_comment_moderation_job(self.db, comment),
            ai_queue.enqueue_forum_thread_moderation_job(self.db, thread),
            ai_queue.enqueue_forum_reply_moderation_job(self.db, reply),
        ]
        for job in jobs:
            job.max_attempts = 1
        self.db.commit()

        with patch.object(
            ai_queue.moderation,
            "moderate_post_with_logging",
            side_effect=RuntimeError("moderation provider down"),
        ), patch.object(
            ai_queue.moderation,
            "moderate_comment_with_logging",
            side_effect=RuntimeError("moderation provider down"),
        ), patch.object(
            ai_queue.moderation,
            "moderate_forum_thread_with_logging",
            side_effect=RuntimeError("moderation provider down"),
        ), patch.object(
            ai_queue.moderation,
            "moderate_forum_reply_with_logging",
            side_effect=RuntimeError("moderation provider down"),
        ):
            for _ in jobs:
                self.assertEqual(ai_queue.process_ai_jobs(self.db, limit=1, worker="test-worker"), 1)

        for item in (post, comment, thread, reply):
            self.db.refresh(item)
            self.assertEqual(item.moderation_status, "flagged")
            self.assertEqual(item.toxicity_score, 0.0)
            self.assertIn("manual review", item.moderation_reason)
        self.assertFalse(comment.approved)

        failed_jobs = self.db.query(models.AIJob).filter(models.AIJob.id.in_([job.id for job in jobs])).all()
        self.assertEqual({job.status for job in failed_jobs}, {"failed"})
        self.assertEqual(self.db.query(models.GologaniTransaction).count(), 0)
        queued_followups = self.db.query(models.AIJob).filter(
            models.AIJob.job_type == ai_queue.JOB_AI_CRITIC
        ).count()
        self.assertEqual(queued_followups, 0)


if __name__ == "__main__":
    unittest.main()
