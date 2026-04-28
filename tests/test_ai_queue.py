import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

from app import ai_queue, crud, models, moderation, schemas


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
        post = crud.create_user_post(
            self.db,
            schemas.PostCreate(title="Poem", content="Un text pentru coadă.", ai_critic=True),
            user_id=user.id,
        )
        ai_queue.enqueue_post_publish_job(self.db, post, ai_critic_requested=True)
        approved = SimpleNamespace(
            status=moderation.ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason="ok",
        )

        with patch.dict(os.environ, {"AUDIO_ENABLED": "True"}), patch.object(
            ai_queue.category_classifier, "classify_post", return_value="poezie"
        ), patch.object(ai_queue.moderation, "moderate_post_with_logging", return_value=approved):
            processed = ai_queue.process_ai_jobs(self.db, limit=1, worker="test-worker")

        self.assertEqual(processed, 1)
        self.db.refresh(post)
        self.assertEqual(post.moderation_status, "approved")
        self.assertEqual(post.category, "poezie")
        self.assertTrue(post.ai_critic_requested)
        self.assertEqual(self.db.query(models.PostAudio).filter_by(post_id=post.id, source="tts").count(), 0)
        queued_types = {
            job.job_type
            for job in self.db.query(models.AIJob).filter(models.AIJob.status == "pending").all()
        }
        self.assertIn(ai_queue.JOB_THEME_ANALYSIS, queued_types)
        self.assertIn(ai_queue.JOB_AI_CRITIC, queued_types)
        self.assertNotIn(ai_queue.JOB_TTS_AUDIO, queued_types)
        self.assertEqual(self.db.query(models.GologaniTransaction).filter_by(source_type="post").count(), 1)

    def test_comment_moderation_job_updates_comment_without_blocking_create(self):
        user = self.make_user()
        post = crud.create_user_post(
            self.db,
            schemas.PostCreate(title="Text", content="Conținut", ai_critic=False),
            user_id=user.id,
        )
        post.moderation_status = "approved"
        self.db.commit()
        comment = crud.create_comment(
            self.db,
            schemas.CommentCreate(content="Comentariu curat"),
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


if __name__ == "__main__":
    unittest.main()
