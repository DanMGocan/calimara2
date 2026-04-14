import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

from app import auth, crud, models, schemas
from app.routers import auth_routes


class DummyRequest:
    def __init__(self, session):
        self.session = session


class BackendStabilizationTests(unittest.TestCase):
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
        auth._db_epoch_cache = ""

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def make_user(self, username: str) -> models.User:
        user = models.User(
            username=username,
            email=f"{username}@example.com",
            google_id=f"google-{username}",
            subtitle=f"subtitle-{username}",
            avatar_seed=f"seed-{username}",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def make_post(
        self,
        user: models.User,
        title: str,
        *,
        moderation_status: str = "approved",
        theme_analysis_status: str = "completed",
        themes=None,
        feelings=None,
    ) -> models.Post:
        self.slug_counter += 1
        post = models.Post(
            user_id=user.id,
            title=title,
            slug=f"{title.lower().replace(' ', '-')}-{self.slug_counter}",
            content=f"content for {title}",
            category="proza_scurta",
            moderation_status=moderation_status,
            theme_analysis_status=theme_analysis_status,
            themes=themes or [],
            feelings=feelings or [],
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def test_get_current_user_uses_id_lookup_and_clears_missing_sessions(self):
        user = self.make_user("alice")

        current_user = auth.get_current_user(DummyRequest({"user_id": user.id}), self.db)
        self.assertIsNotNone(current_user)
        self.assertEqual(current_user.id, user.id)

        missing_request = DummyRequest({"user_id": 999_999})
        self.assertIsNone(auth.get_current_user(missing_request, self.db))
        self.assertEqual(missing_request.session, {})

    def test_google_user_creation_and_request_schemas_accept_partial_payloads(self):
        created_user = crud.create_user_from_google(
            self.db,
            {
                "username": "googleuser",
                "email": "google@example.com",
                "google_id": "google-123",
                "subtitle": "new user",
                "avatar_seed": "seed-google",
            },
        )

        self.assertEqual(created_user.username, "googleuser")
        self.assertEqual(crud.get_user_by_id(self.db, created_user.id).email, "google@example.com")

        alias_payload = schemas.MessageToUser.model_validate({"username": "reader", "content": "Salut"})
        canonical_payload = schemas.MessageToUser.model_validate(
            {"recipient_username": "reader", "content": "Salut"}
        )
        profile_update = schemas.UserProfileUpdate.model_validate({"avatar_seed": "new-seed"})

        self.assertEqual(alias_payload.recipient_username, "reader")
        self.assertEqual(canonical_payload.recipient_username, "reader")
        self.assertEqual(profile_update.avatar_seed, "new-seed")
        self.assertIsNone(profile_update.subtitle)

    def test_google_login_redirects_with_sync_auth_url_helper(self):
        request = DummyRequest({})

        with patch.object(
            auth_routes.google_oauth,
            "get_google_auth_url",
            return_value="https://accounts.google.com/o/oauth2/auth?client_id=test",
        ):
            response = self.async_run(auth_routes.google_login.__wrapped__(request))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["location"],
            "https://accounts.google.com/o/oauth2/auth?client_id=test",
        )

    def test_theme_and_tag_helpers_return_normalized_deduplicated_values(self):
        author = self.make_user("writer")
        post = self.make_post(
            author,
            "Themes",
            themes=["Dor", "timp", "dor"],
            feelings=["Nostalgie", "bucurie", "nostalgie"],
        )
        self.make_post(
            author,
            "Ignored",
            moderation_status="pending",
            themes=["should-not-appear"],
            feelings=["should-not-appear"],
        )

        crud.create_tag(self.db, post.id, "dragoste")
        crud.create_tag(self.db, post.id, "Dragoste")
        crud.create_tag(self.db, post.id, "drama")
        crud.create_tag(self.db, post.id, "dor")

        self.assertEqual(crud.get_distinct_themes(self.db), ["dor", "timp"])
        self.assertEqual(crud.get_distinct_feelings(self.db), ["bucurie", "nostalgie"])
        self.assertEqual(crud.get_tag_suggestions(self.db, "dr"), ["dragoste", "drama"])

    def test_comment_helpers_approve_and_delete_comments(self):
        author = self.make_user("author")
        post = self.make_post(author, "Post")
        comment = models.Comment(
            post_id=post.id,
            author_name="Guest",
            author_email="guest@example.com",
            content="Please approve me",
            approved=False,
            moderation_status="pending",
        )
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)

        approved_comment = crud.approve_comment(self.db, comment.id)
        self.assertTrue(approved_comment.approved)
        self.assertEqual(approved_comment.moderation_status, "approved")

        deleted_comment = crud.delete_comment(self.db, comment.id)
        self.assertEqual(deleted_comment.id, comment.id)
        self.assertIsNone(self.db.query(models.Comment).filter(models.Comment.id == comment.id).first())

    def test_message_crud_restores_conversation_lifecycle(self):
        alice = self.make_user("alice")
        bob = self.make_user("bob")
        carol = self.make_user("carol")

        self.assertIsNone(crud.send_message_to_user(self.db, alice.id, "alice", "self"))

        first_message = crud.send_message_to_user(self.db, alice.id, "bob", "hello bob")
        conversation = self.db.query(models.Conversation).first()
        self.assertIsNotNone(first_message)
        self.assertEqual(conversation.user1_id, min(alice.id, bob.id))
        self.assertEqual(conversation.user2_id, max(alice.id, bob.id))

        reply = crud.send_message_to_user(self.db, bob.id, "alice", "reply to alice")
        self.assertEqual(reply.conversation_id, conversation.id)
        self.assertEqual(self.db.query(models.Conversation).count(), 1)
        self.assertEqual(crud.get_unread_message_count(self.db, alice.id), 1)

        conversations = crud.get_user_conversations(self.db, alice.id)
        self.assertEqual(len(conversations), 1)
        self.assertEqual(conversations[0]._latest_message.id, reply.id)

        searched = crud.search_conversations(self.db, alice.id, "reply")
        self.assertEqual([conv.id for conv in searched], [conversation.id])

        messages = crud.get_conversation_messages(self.db, conversation.id, alice.id)
        self.assertEqual([message.id for message in messages], [reply.id, first_message.id])
        self.assertEqual(crud.mark_messages_as_read(self.db, conversation.id, alice.id), 1)
        self.assertEqual(crud.get_unread_message_count(self.db, alice.id), 0)

        third_message = crud.create_message(self.db, conversation.id, alice.id, "third message")
        self.assertIsNotNone(third_message)
        self.assertIsNone(crud.get_conversation_by_id(self.db, conversation.id, carol.id))
        self.assertFalse(crud.delete_conversation(self.db, conversation.id, carol.id))
        self.assertTrue(crud.delete_conversation(self.db, conversation.id, alice.id))
        self.assertEqual(self.db.query(models.Conversation).count(), 0)
        self.assertEqual(self.db.query(models.Message).count(), 0)

    def test_notifications_and_moderation_helpers_support_pagination_and_stats(self):
        user = self.make_user("moderated")

        older = crud.create_notification(self.db, user.id, "older", "Old notification")
        newer = crud.create_notification(self.db, user.id, "newer", "New notification")
        older.created_at = datetime.now(timezone.utc) - timedelta(days=1)
        newer.created_at = datetime.now(timezone.utc)
        self.db.commit()

        first_page = crud.get_notifications_for_user(self.db, user.id, skip=0, limit=1)
        second_page = crud.get_notifications_for_user(self.db, user.id, skip=1, limit=1)
        self.assertEqual([notification.title for notification in first_page], ["New notification"])
        self.assertEqual([notification.title for notification in second_page], ["Old notification"])

        log_approved = models.ModerationLog(
            content_type="post",
            content_id=1,
            user_id=user.id,
            ai_decision="approved",
            human_decision="approved",
            toxicity_score=0.1,
        )
        log_pending = models.ModerationLog(
            content_type="comment",
            content_id=2,
            user_id=user.id,
            ai_decision="flagged",
            human_decision=None,
            toxicity_score=0.9,
        )
        log_rejected = models.ModerationLog(
            content_type="post",
            content_id=3,
            user_id=user.id,
            ai_decision="rejected",
            human_decision="rejected",
            toxicity_score=0.5,
        )
        self.db.add_all([log_approved, log_pending, log_rejected])
        self.db.commit()

        approved_logs = crud.get_moderation_logs_by_decision(self.db, "approved")
        pending_logs = crud.get_moderation_logs_by_decision(self.db, "pending")
        stats = crud.get_moderation_stats_extended(self.db)

        self.assertEqual([log.id for log in approved_logs], [log_approved.id])
        self.assertEqual([log.id for log in pending_logs], [log_pending.id])
        self.assertEqual(stats["total_logs"], 3)
        self.assertEqual(stats["pending_review_count"], 1)
        self.assertEqual(stats["ai_decisions"]["flagged"], 1)
        self.assertEqual(stats["human_decisions"]["approved"], 1)
        self.assertGreater(stats["scores"]["average_toxicity"], 0)

    @staticmethod
    def async_run(awaitable):
        import asyncio

        return asyncio.run(awaitable)


if __name__ == "__main__":
    unittest.main()
