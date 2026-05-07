import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET_KEY", "test-secret")

from app import crud, email_service, models, schemas
from app.routers import admin_routes


class EmailSystemTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        models.Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.SessionLocal()
        self.slug_counter = 0

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def make_user(self, username: str, **kwargs) -> models.User:
        user = models.User(
            username=username,
            email=f"{username}@example.com",
            google_id=f"google-{username}",
            **kwargs,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def make_post(self, owner: models.User, title: str = "Post") -> models.Post:
        self.slug_counter += 1
        post = models.Post(
            user_id=owner.id,
            title=title,
            slug=f"{title.lower()}-{self.slug_counter}",
            content="Text",
            category="poezie",
            moderation_status="approved",
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def test_comment_and_mention_emails_queue_after_public_approval(self):
        owner = self.make_user("owner")
        commenter = self.make_user("commenter")
        mentioned = self.make_user("mentioned")
        post = self.make_post(owner)
        comment = crud.create_comment(
            self.db,
            schemas.CommentCreate(content="<p>Salut @mentioned.</p>"),
            post_id=post.id,
            user_id=commenter.id,
        )

        self.assertEqual(self.db.query(models.EmailOutbox).count(), 0)
        crud.approve_comment(self.db, comment.id)

        rows = self.db.query(models.EmailOutbox).order_by(models.EmailOutbox.email_type.asc()).all()
        self.assertEqual([row.email_type for row in rows], ["comment", "mention"])
        self.assertEqual(rows[0].recipient_user_id, owner.id)
        self.assertEqual(rows[1].recipient_user_id, mentioned.id)

        crud.approve_comment(self.db, comment.id)
        self.assertEqual(self.db.query(models.EmailOutbox).count(), 2)

    def test_unsubscribe_token_updates_matching_preference(self):
        user = self.make_user("subscriber")
        token = email_service.unsubscribe_token(user.id, email_service.EMAIL_TYPE_ANALYTICS)

        updated, email_type = email_service.apply_unsubscribe_token(
            self.db,
            token,
            requested_type=email_service.EMAIL_TYPE_ANALYTICS,
        )

        self.assertEqual(email_type, email_service.EMAIL_TYPE_ANALYTICS)
        self.assertFalse(updated.email_analytics_digest)
        self.assertTrue(updated.email_comment_notifications)

    def test_worker_sends_queued_email_and_stores_provider_id(self):
        user = self.make_user("mailtarget")
        email_service.queue_email(
            self.db,
            recipient_user_id=user.id,
            recipient_email=user.email,
            recipient_name=user.username,
            subject="Test",
            html_content="<p>Hello</p>",
            email_type="admin",
        )

        with patch.dict(os.environ, {"EMAILS_ENABLED": "True"}), patch.object(
            email_service,
            "_send_with_brevo",
            return_value="message-id-1",
        ):
            processed = email_service.process_email_outbox(self.db, limit=5, worker="test-worker")

        row = self.db.query(models.EmailOutbox).one()
        self.assertEqual(processed, 1)
        self.assertEqual(row.status, "sent")
        self.assertEqual(row.provider_message_id, "message-id-1")

    def test_admin_campaign_filters_by_posts_and_opt_outs(self):
        admin = self.make_user("admin", is_admin=True, is_moderator=True)
        target = self.make_user("target")
        opted_out = self.make_user("optedout", email_admin_announcements=False)
        low_posts = self.make_user("lowposts")
        suspended = self.make_user("suspended", is_suspended=True)
        for index in range(2):
            self.make_post(target, f"Target {index}")
            self.make_post(opted_out, f"Opted {index}")
            self.make_post(suspended, f"Suspended {index}")
        self.make_post(low_posts, "Low")

        audience = schemas.AdminEmailAudience(status="active", min_posts=2)
        preview = admin_routes.preview_admin_email(
            schemas.AdminEmailPreviewRequest(audience=audience),
            db=self.db,
            current_user=admin,
        )
        self.assertEqual(preview["matched_count"], 2)
        self.assertEqual(preview["recipient_count"], 1)
        self.assertEqual(preview["sample"][0]["username"], "target")

        result = admin_routes.create_admin_email_campaign(
            schemas.AdminEmailCampaignCreate(
                audience=audience,
                subject="Anunț",
                html_content="<p>Salut</p>",
            ),
            request=None,
            db=self.db,
            current_user=admin,
        )
        self.assertEqual(result["queued_count"], 1)
        self.assertEqual(self.db.query(models.EmailCampaign).count(), 1)
        self.assertEqual(self.db.query(models.EmailOutbox).filter_by(email_type="admin").count(), 1)


if __name__ == "__main__":
    unittest.main()
