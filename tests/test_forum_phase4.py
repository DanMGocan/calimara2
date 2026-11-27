import os
import unittest
from datetime import timedelta
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

from app import ai_queue, crud, models, moderation, schemas
from app.routers import forum_routes
from app.week_util import utcnow_naive


def _request(method: str = "PUT") -> Request:
    return Request({"type": "http", "method": method, "path": "/", "headers": [], "client": ("127.0.0.1", 1234)})


class ForumPhase4Tests(unittest.TestCase):
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
        self.approved = SimpleNamespace(status=moderation.ModerationStatus.APPROVED, toxicity_score=0.0, reason="ok")
        self.member = self.user("membru", balance=0)
        self.other = self.user("cititor", balance=0)
        self.third = self.user("urmaritor", balance=0)
        self.mod = self.user("moderator", is_moderator=True)
        self.admin = self.user("admin", is_admin=True)

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def user(self, name, *, is_admin=False, is_moderator=False, is_suspended=False, balance=0):
        user = models.User(
            username=name,
            email=f"{name}@example.com",
            google_id=f"google-{name}",
            is_admin=is_admin,
            is_moderator=is_moderator,
            is_suspended=is_suspended,
            gologani_balance=balance,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def thread(self, author=None, section="general", title="Discuție", content="<p>Conținut</p>", approve=True):
        thread = crud.create_forum_thread(
            self.db,
            author or self.member,
            schemas.ForumThreadCreate(section=section, title=title, content=content),
        )
        if approve:
            crud.apply_forum_thread_moderation_result(self.db, thread, self.approved)
        return thread

    def reply(self, thread, author=None, content="<p>Răspuns</p>", approve=True):
        reply, error = crud.create_forum_reply(
            self.db, author or self.other, thread, schemas.ForumReplyCreate(content=content)
        )
        self.assertIsNone(error)
        if approve:
            crud.apply_forum_reply_moderation_result(self.db, reply, self.approved)
        return reply

    # editing -------------------------------------------------------------

    def test_edit_thread_within_window_preserves_slug_queues_moderation_and_skips_repeat_rewards(self):
        thread = self.thread(author=self.member, title="Titlu inițial", content="<p>Salut @cititor</p>")
        original_slug = thread.slug
        original_activity = thread.last_activity_at
        self.db.refresh(self.member)
        balance_after_create = self.member.gologani_balance
        notifications_before = self.db.query(models.Notification).count()

        payload = forum_routes.update_forum_thread_api.__wrapped__(
            _request("PUT"),
            thread.id,
            schemas.ForumThreadUpdate(title="Titlu editat", content="<p>Text actualizat pentru @cititor</p>"),
            db=self.db,
            current_user=self.member,
        )
        self.assertEqual(payload["slug"], original_slug)
        self.assertEqual(payload["title"], "Titlu editat")
        self.assertEqual(payload["moderation_status"], "pending")
        self.assertIsNotNone(payload["edited_at"])
        self.assertTrue(payload["can_edit"])

        jobs = (
            self.db.query(models.AIJob)
            .filter(models.AIJob.job_type == ai_queue.JOB_FORUM_THREAD_MODERATION, models.AIJob.target_id == thread.id)
            .all()
        )
        self.assertEqual(len(jobs), 1)

        # Re-approval of an edited thread does not bump activity, re-award Gologani, or re-notify mentions.
        self.db.refresh(thread)
        thread.last_activity_at = original_activity - timedelta(minutes=10)
        self.db.commit()
        activity_before_reapprove = thread.last_activity_at

        crud.apply_forum_thread_moderation_result(self.db, thread, self.approved)
        self.db.refresh(thread)
        self.db.refresh(self.member)
        self.assertEqual(thread.last_activity_at, activity_before_reapprove)
        self.assertEqual(self.member.gologani_balance, balance_after_create)
        self.assertEqual(self.db.query(models.Notification).count(), notifications_before)

    def test_edit_reply_permissions_time_window_locked_archived_and_reapproval(self):
        thread = self.thread(author=self.member)
        reply = self.reply(thread, author=self.other, content="<p>Răspuns inițial @membru</p>")
        self.db.refresh(self.other)
        balance_before = self.other.gologani_balance
        notifications_before = self.db.query(models.Notification).count()

        # Non-author cannot edit.
        with self.assertRaises(HTTPException) as raised:
            forum_routes.update_forum_reply_api.__wrapped__(
                _request("PUT"),
                reply.id,
                schemas.ForumReplyUpdate(content="<p>Alt text</p>"),
                db=self.db,
                current_user=self.third,
            )
        self.assertEqual(raised.exception.status_code, 403)

        # Author edits within 30 minutes.
        updated = forum_routes.update_forum_reply_api.__wrapped__(
            _request("PUT"),
            reply.id,
            schemas.ForumReplyUpdate(content="<p>Răspuns editat @membru</p>"),
            db=self.db,
            current_user=self.other,
        )
        self.assertEqual(updated["moderation_status"], "pending")
        self.assertIsNotNone(updated["edited_at"])

        # Re-approval does not re-award Gologani or re-send notifications.
        self.db.refresh(reply)
        crud.apply_forum_reply_moderation_result(self.db, reply, self.approved)
        self.db.refresh(self.other)
        self.assertEqual(self.other.gologani_balance, balance_before)
        self.assertEqual(self.db.query(models.Notification).count(), notifications_before)

        # Expired 30-minute window blocks author, allows moderator.
        reply.created_at = utcnow_naive() - timedelta(minutes=31)
        self.db.commit()
        with self.assertRaises(HTTPException) as raised:
            forum_routes.update_forum_reply_api.__wrapped__(
                _request("PUT"),
                reply.id,
                schemas.ForumReplyUpdate(content="<p>Prea târziu</p>"),
                db=self.db,
                current_user=self.other,
            )
        self.assertEqual(raised.exception.status_code, 403)

        mod_updated = forum_routes.update_forum_reply_api.__wrapped__(
            _request("PUT"),
            reply.id,
            schemas.ForumReplyUpdate(content="<p>Editat de moderator</p>"),
            db=self.db,
            current_user=self.mod,
        )
        self.assertEqual(mod_updated["moderation_status"], "pending")

        # Locked thread blocks author edit, allows moderator.
        reply.created_at = utcnow_naive()
        thread.is_locked = True
        self.db.commit()
        with self.assertRaises(HTTPException) as raised:
            forum_routes.update_forum_reply_api.__wrapped__(
                _request("PUT"),
                reply.id,
                schemas.ForumReplyUpdate(content="<p>Fir închis</p>"),
                db=self.db,
                current_user=self.other,
            )
        self.assertEqual(raised.exception.status_code, 403)

        # Archived section blocks author edit.
        thread.is_locked = False
        section = crud.get_forum_section_by_slug(self.db, "general")
        section.is_archived = True
        self.db.commit()
        with self.assertRaises(HTTPException) as raised:
            forum_routes.update_forum_reply_api.__wrapped__(
                _request("PUT"),
                reply.id,
                schemas.ForumReplyUpdate(content="<p>Secțiune arhivată</p>"),
                db=self.db,
                current_user=self.other,
            )
        self.assertEqual(raised.exception.status_code, 403)

        # Rejected item returns 404.
        reply.moderation_status = "rejected"
        self.db.commit()
        with self.assertRaises(HTTPException) as raised:
            forum_routes.update_forum_reply_api.__wrapped__(
                _request("PUT"),
                reply.id,
                schemas.ForumReplyUpdate(content="<p>Respins</p>"),
                db=self.db,
                current_user=self.mod,
            )
        self.assertEqual(raised.exception.status_code, 404)

    # following -----------------------------------------------------------

    def test_follow_thread_notifies_followers_without_duplicating_author_or_suspended(self):
        thread = self.thread(author=self.member)
        suspended = self.user("suspendat", is_suspended=True)

        # Author also follows — must still get only 1 notification when someone replies.
        forum_routes.follow_forum_thread_api.__wrapped__(_request("POST"), thread.id, db=self.db, current_user=self.member)
        res = forum_routes.follow_forum_thread_api.__wrapped__(_request("POST"), thread.id, db=self.db, current_user=self.third)
        self.assertTrue(res["is_following"])
        self.assertEqual(res["follower_count"], 2)
        # Idempotent follow.
        res_again = forum_routes.follow_forum_thread_api.__wrapped__(_request("POST"), thread.id, db=self.db, current_user=self.third)
        self.assertEqual(res_again["follower_count"], 2)
        forum_routes.follow_forum_thread_api.__wrapped__(_request("POST"), thread.id, db=self.db, current_user=suspended)

        detail = forum_routes.get_forum_thread_api(thread.slug, db=self.db, current_user=self.third)
        self.assertTrue(detail["is_following"])
        self.assertEqual(detail["follower_count"], 3)

        reply = self.reply(thread, author=self.other)
        member_notifs = self.db.query(models.Notification).filter(models.Notification.user_id == self.member.id).all()
        third_notifs = self.db.query(models.Notification).filter(models.Notification.user_id == self.third.id).all()
        other_notifs = self.db.query(models.Notification).filter(models.Notification.user_id == self.other.id).all()
        suspended_notifs = self.db.query(models.Notification).filter(models.Notification.user_id == suspended.id).all()

        self.assertEqual(len(member_notifs), 1)
        self.assertEqual(len(third_notifs), 1)
        self.assertEqual(third_notifs[0].link, f"/discutii/{thread.slug}#reply-{reply.id}")
        self.assertEqual(len(other_notifs), 0)
        self.assertEqual(len(suspended_notifs), 0)

        # Unfollow stops subsequent notifications.
        unfollow_res = forum_routes.unfollow_forum_thread_api.__wrapped__(
            _request("DELETE"), thread.id, db=self.db, current_user=self.third
        )
        self.assertFalse(unfollow_res["is_following"])
        self.reply(thread, author=self.other)
        self.assertEqual(
            self.db.query(models.Notification).filter(models.Notification.user_id == self.third.id).count(),
            1,
        )

    # jump to first unread ------------------------------------------------

    def test_jump_to_first_unread_across_pages_and_list_badge(self):
        thread = self.thread(author=self.member)
        now = utcnow_naive()
        thread.last_activity_at = now - timedelta(hours=2)
        self.db.commit()

        # First 20 replies (page 1) read by member.
        initial_replies = []
        for idx in range(forum_routes.REPLIES_PER_PAGE):
            r = self.reply(thread, author=self.other, content=f"<p>Inițial {idx + 1}</p>")
            r.created_at = now - timedelta(minutes=90 - idx)
            initial_replies.append(r)
        thread.last_activity_at = now - timedelta(minutes=60)
        self.db.commit()

        forum_routes.get_forum_thread_api(thread.slug, db=self.db, current_user=self.member)

        # Two new replies arrive after the read mark -> reply #21 lands on page 2.
        unread_1 = self.reply(thread, author=self.other, content="<p>Necitit 1</p>")
        unread_1.created_at = now - timedelta(minutes=20)
        unread_2 = self.reply(thread, author=self.other, content="<p>Necitit 2</p>")
        unread_2.created_at = now - timedelta(minutes=10)
        thread.last_activity_at = now - timedelta(minutes=10)
        self.db.commit()

        listing = forum_routes.list_forum_threads_api(section="general", db=self.db, current_user=self.member)
        self.assertTrue(listing["threads"][0]["has_new_replies"])
        self.assertEqual(listing["threads"][0]["first_unread_reply_id"], unread_1.id)

        detail = forum_routes.get_forum_thread_api(thread.slug, unread=True, db=self.db, current_user=self.member)
        self.assertEqual(detail["reply_page"], 2)
        self.assertEqual(detail["first_unread_reply_id"], unread_1.id)
        self.assertEqual([item["id"] for item in detail["replies"]], [unread_1.id, unread_2.id])

        # Opening the thread marked it read; next visit has no unread replies.
        listing_after = forum_routes.list_forum_threads_api(section="general", db=self.db, current_user=self.member)
        self.assertFalse(listing_after["threads"][0]["has_new_replies"])
        self.assertIsNone(listing_after["threads"][0]["first_unread_reply_id"])

    # reply likes ---------------------------------------------------------

    def test_reply_likes_toggle_rules_and_pinned_sync(self):
        thread = self.thread(author=self.member)
        reply = self.reply(thread, author=self.other, content="<p>Util</p>")
        pending_reply = self.reply(thread, author=self.other, content="<p>Pending</p>", approve=False)
        crud.update_forum_reply_state(self.db, self.mod, reply, "pin")

        self.db.refresh(self.member)
        self.db.refresh(self.other)
        member_balance = self.member.gologani_balance
        other_balance = self.other.gologani_balance

        like_res = forum_routes.like_forum_reply_api.__wrapped__(
            _request("POST"), reply.id, db=self.db, current_user=self.member
        )
        self.assertEqual(like_res, {"reply_id": reply.id, "like_count": 1, "liked_by_me": True})

        # Idempotent repeat like.
        like_again = forum_routes.like_forum_reply_api.__wrapped__(
            _request("POST"), reply.id, db=self.db, current_user=self.member
        )
        self.assertEqual(like_again["like_count"], 1)

        # No Gologani awarded for reply likes.
        self.db.refresh(self.member)
        self.db.refresh(self.other)
        self.assertEqual(self.member.gologani_balance, member_balance)
        self.assertEqual(self.other.gologani_balance, other_balance)

        # Detail includes like counts on both replies and pinned_replies.
        detail = forum_routes.get_forum_thread_api(thread.slug, db=self.db, current_user=self.member)
        self.assertEqual(detail["replies"][0]["like_count"], 1)
        self.assertTrue(detail["replies"][0]["liked_by_me"])
        self.assertTrue(detail["replies"][0]["can_like"])
        self.assertEqual(detail["pinned_replies"][0]["like_count"], 1)
        self.assertTrue(detail["pinned_replies"][0]["liked_by_me"])

        # Self-like is blocked.
        with self.assertRaises(HTTPException) as raised:
            forum_routes.like_forum_reply_api.__wrapped__(
                _request("POST"), reply.id, db=self.db, current_user=self.other
            )
        self.assertEqual(raised.exception.status_code, 400)

        # Pending reply cannot be liked.
        with self.assertRaises(HTTPException) as raised:
            forum_routes.like_forum_reply_api.__wrapped__(
                _request("POST"), pending_reply.id, db=self.db, current_user=self.member
            )
        self.assertEqual(raised.exception.status_code, 400)

        # Unlike clears count.
        unlike_res = forum_routes.unlike_forum_reply_api.__wrapped__(
            _request("DELETE"), reply.id, db=self.db, current_user=self.member
        )
        self.assertEqual(unlike_res, {"reply_id": reply.id, "like_count": 0, "liked_by_me": False})

    # quote sanitization --------------------------------------------------

    def test_blockquote_reply_survives_sanitization(self):
        quote = "<blockquote><p><strong>cititor (#1) a scris:</strong> Text citat</p></blockquote><p>Răspunsul meu</p>"
        payload = schemas.ForumReplyCreate(content=quote)
        self.assertIn("<blockquote>", payload.content)
        self.assertIn("<strong>cititor (#1) a scris:</strong>", payload.content)


if __name__ == "__main__":
    unittest.main()
