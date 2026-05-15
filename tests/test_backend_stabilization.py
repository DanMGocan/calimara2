import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET_KEY", "test-secret")

from app import auth, crud, local_auth, models, moderation, schemas, statistics
from app.routers import admin_routes, api_pages, auth_routes, follow_routes, forum_routes, friend_routes, moderation_routes, post_routes, series_routes, user_routes


class DummyRequest:
    def __init__(self, session, scheme="http", headers=None, cookies=None, client_host="127.0.0.1"):
        self.session = session
        self.url = SimpleNamespace(scheme=scheme)
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.client = SimpleNamespace(host=client_host)


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
        auth._db_epoch_mtime = None

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
        category: str = "proza_scurta",
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
            category=category,
            moderation_status=moderation_status,
            theme_analysis_status=theme_analysis_status,
            themes=themes or [],
            feelings=feelings or [],
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def make_series(self, owner: models.User, title: str = "Series") -> models.Series:
        series = crud.create_series(
            self.db,
            owner_id=owner.id,
            data=schemas.SeriesCreate(title=title, description="series description"),
        )
        self.db.refresh(series)
        return series

    def test_series_are_owner_only_and_public_pages_hide_unapproved_posts(self):
        owner = self.make_user("seriesowner")
        other = self.make_user("seriesother")
        series = self.make_series(owner, "Owner Series")
        approved = self.make_post(owner, "Approved Chapter")
        pending = self.make_post(owner, "Pending Chapter", moderation_status="pending")
        other_post = self.make_post(other, "Other Chapter")

        first_entry = series_routes.add_post_to_series_api(
            series.id,
            schemas.SeriesAddPostRequest(post_id=approved.id),
            db=self.db,
            current_user=owner,
        )
        second_entry = series_routes.add_post_to_series_api(
            series.id,
            schemas.SeriesAddPostRequest(post_id=pending.id),
            db=self.db,
            current_user=owner,
        )

        self.assertEqual(first_entry["position"], 1)
        self.assertEqual(second_entry["position"], 2)

        with self.assertRaises(HTTPException) as wrong_author:
            series_routes.add_post_to_series_api(
                series.id,
                schemas.SeriesAddPostRequest(post_id=other_post.id),
                db=self.db,
                current_user=owner,
            )
        self.assertEqual(wrong_author.exception.status_code, 403)

        public_payload = series_routes.get_series_by_slug_api(series.slug, db=self.db)
        self.assertEqual([entry["post"]["slug"] for entry in public_payload["posts"]], [approved.slug])

        managed_payload = series_routes.manage_my_series(series.id, db=self.db, current_user=owner)
        self.assertEqual([entry["post"]["moderation_status"] for entry in managed_payload["posts"]], ["approved", "pending"])

    def test_series_reorder_and_single_series_per_post(self):
        owner = self.make_user("serieseditor")
        series = self.make_series(owner, "Editable Series")
        other_series = self.make_series(owner, "Other Series")
        first = self.make_post(owner, "First Chapter")
        second = self.make_post(owner, "Second Chapter")

        series_routes.add_post_to_series_api(
            series.id,
            schemas.SeriesAddPostRequest(post_id=first.id),
            db=self.db,
            current_user=owner,
        )
        series_routes.add_post_to_series_api(
            series.id,
            schemas.SeriesAddPostRequest(post_id=second.id),
            db=self.db,
            current_user=owner,
        )

        reordered = series_routes.reorder_series_posts_api(
            series.id,
            schemas.SeriesReorderRequest(post_ids=[second.id, first.id]),
            db=self.db,
            current_user=owner,
        )
        self.assertEqual([entry["post_id"] for entry in reordered["posts"]], [second.id, first.id])

        with self.assertRaises(HTTPException) as already_used:
            series_routes.add_post_to_series_api(
                other_series.id,
                schemas.SeriesAddPostRequest(post_id=first.id),
                db=self.db,
                current_user=owner,
            )
        self.assertEqual(already_used.exception.status_code, 409)

        context = series_routes.get_post_series(first.id, db=self.db, current_user=None)
        self.assertEqual(context["series"]["slug"], series.slug)
        self.assertEqual(context["position"], 2)
        self.assertEqual(context["previous_post"]["id"], second.id)

    def test_profile_and_moderation_routes_preserve_http_errors(self):
        user = self.make_user("profileuser")
        admin = self.make_user("adminuser")
        admin.is_admin = True
        self.db.commit()

        with self.assertRaises(HTTPException) as featured_error:
            user_routes.update_featured_posts(
                schemas.FeaturedPostsUpdate(post_ids=[999_999]),
                db=self.db,
                current_user=user,
            )
        self.assertEqual(featured_error.exception.status_code, 400)

        with self.assertRaises(HTTPException) as unsuspend_error:
            moderation_routes.unsuspend_user(
                999_999,
                db=self.db,
                current_user=admin,
            )
        self.assertEqual(unsuspend_error.exception.status_code, 404)

    def test_profile_promotions_cover_all_slot_types(self):
        owner = self.make_user("promoter")
        peer = self.make_user("peerwriter")
        target = self.make_user("targetwriter")
        third = self.make_user("thirdwriter")
        own_posts = [self.make_post(owner, f"Own Text {index}") for index in range(1, 3)]
        extra_own_post = self.make_post(owner, "Own Text Three")
        peer_post = self.make_post(peer, "Peer Text")
        target_post = self.make_post(target, "Target Text")
        third_post = self.make_post(third, "Third Text")

        payload = user_routes.update_my_promotions(
            schemas.UserPromotionsUpdate(
                own_post_ids=[post.id for post in own_posts],
                author_ids=[peer.id, target.id, third.id],
                other_post_ids=[peer_post.id, target_post.id, third_post.id],
            ),
            db=self.db,
            current_user=owner,
        )

        self.assertEqual(len(payload["own_posts"]), 2)
        self.assertEqual(len(payload["authors"]), 3)
        self.assertEqual(len(payload["other_posts"]), 3)

        blog_payload = api_pages.blog_data(
            DummyRequest(session={}),
            owner.username,
            db=self.db,
            current_user=owner,
        )
        self.assertEqual(len(blog_payload["promoted_own_posts"]), 2)
        self.assertEqual(len(blog_payload["promoted_authors"]), 3)
        self.assertEqual(len(blog_payload["promoted_external_posts"]), 3)

        with self.assertRaises(HTTPException) as own_limit:
            user_routes.add_promoted_post(
                extra_own_post.id,
                db=self.db,
                current_user=owner,
            )
        self.assertEqual(own_limit.exception.status_code, 400)

    def test_friend_request_lifecycle_and_profile_context(self):
        alice = self.make_user("alicefriend")
        bob = self.make_user("bobfriend")

        sent = friend_routes.send_friend_request(bob.id, db=self.db, current_user=alice)
        self.assertEqual(sent["status"], "outgoing_pending")
        self.assertEqual(crud.get_friendship_status_for_viewer(self.db, alice.id, bob.id), "outgoing_pending")
        self.assertEqual(crud.get_friendship_status_for_viewer(self.db, bob.id, alice.id), "incoming_pending")
        self.assertEqual(crud.get_incoming_friend_request_count(self.db, bob.id), 1)
        self.assertEqual(self.db.query(models.Notification).filter_by(user_id=bob.id, type="friend_request").count(), 1)

        friendship_id = sent["friendship"]["id"]
        accepted = friend_routes.accept_friend_request(friendship_id, db=self.db, current_user=bob)
        self.assertEqual(accepted["status"], "friends")
        self.assertEqual(crud.get_friendship_status_for_viewer(self.db, alice.id, bob.id), "friends")
        self.assertEqual(crud.get_friend_count_for_user(self.db, alice.id), 1)
        self.assertEqual(crud.get_friend_count_for_user(self.db, bob.id), 1)
        self.assertEqual(crud.get_incoming_friend_request_count(self.db, bob.id), 0)
        self.assertEqual(self.db.query(models.Notification).filter_by(user_id=alice.id, type="friend_request_accepted").count(), 1)

        blog_payload = api_pages.blog_data(
            DummyRequest(session={}),
            bob.username,
            db=self.db,
            current_user=alice,
        )
        self.assertEqual(blog_payload["friend_count"], 1)
        self.assertEqual(blog_payload["viewer_friendship_status"], "friends")
        self.assertEqual(blog_payload["viewer_friendship_id"], friendship_id)

        removed = friend_routes.remove_friend(bob.id, db=self.db, current_user=alice)
        self.assertEqual(removed["status"], "none")
        self.assertEqual(crud.get_friendship_status_for_viewer(self.db, alice.id, bob.id), "none")

    def test_friend_request_reverse_send_accepts_existing_request(self):
        alice = self.make_user("reversealice")
        bob = self.make_user("reversebob")

        sent = friend_routes.send_friend_request(bob.id, db=self.db, current_user=alice)
        accepted = friend_routes.send_friend_request(alice.id, db=self.db, current_user=bob)

        self.assertEqual(accepted["status"], "friends")
        self.assertEqual(accepted["friendship"]["id"], sent["friendship"]["id"])
        self.assertEqual(self.db.query(models.Friendship).count(), 1)

    def test_follow_lifecycle_profile_context_and_public_lists(self):
        alice = self.make_user("followalice")
        bob = self.make_user("followbob")
        carmen = self.make_user("followcarmen")

        followed = follow_routes.follow_user(bob.id, db=self.db, current_user=alice)
        self.assertTrue(followed["following"])
        self.assertTrue(crud.is_following(self.db, alice.id, bob.id))
        self.assertEqual(crud.get_follower_count_for_user(self.db, bob.id), 1)
        self.assertEqual(crud.get_following_count_for_user(self.db, alice.id), 1)
        self.assertEqual(self.db.query(models.Notification).filter_by(user_id=bob.id, type="follow").count(), 1)

        duplicate = follow_routes.follow_user(bob.id, db=self.db, current_user=alice)
        self.assertTrue(duplicate["following"])
        self.assertEqual(self.db.query(models.UserFollow).count(), 1)
        self.assertEqual(self.db.query(models.Notification).filter_by(user_id=bob.id, type="follow").count(), 1)

        friend_routes.send_friend_request(carmen.id, db=self.db, current_user=alice)
        self.assertFalse(crud.is_following(self.db, alice.id, carmen.id))

        blog_payload = api_pages.blog_data(
            DummyRequest(session={}),
            bob.username,
            db=self.db,
            current_user=alice,
        )
        self.assertEqual(blog_payload["follower_count"], 1)
        self.assertEqual(blog_payload["following_count"], 0)
        self.assertTrue(blog_payload["viewer_following"])

        followers_payload = follow_routes.get_public_followers(bob.username, db=self.db)
        self.assertEqual(followers_payload["count"], 1)
        self.assertEqual(followers_payload["followers"][0]["username"], alice.username)

        following_payload = follow_routes.get_public_following(alice.username, db=self.db)
        self.assertEqual(following_payload["count"], 1)
        self.assertEqual(following_payload["following"][0]["username"], bob.username)

        unfollowed = follow_routes.unfollow_user(bob.id, db=self.db, current_user=alice)
        self.assertFalse(unfollowed["following"])
        self.assertFalse(crud.is_following(self.db, alice.id, bob.id))
        self.assertEqual(crud.get_follower_count_for_user(self.db, bob.id), 0)

    def test_follow_blocks_self_and_suspended_users(self):
        alice = self.make_user("blockfollowalice")
        suspended = self.make_user("suspendedfollow")
        suspended.is_suspended = True
        self.db.commit()

        with self.assertRaises(HTTPException) as self_error:
            follow_routes.follow_user(alice.id, db=self.db, current_user=alice)
        self.assertEqual(self_error.exception.status_code, 400)

        with self.assertRaises(HTTPException) as suspended_error:
            follow_routes.follow_user(suspended.id, db=self.db, current_user=alice)
        self.assertEqual(suspended_error.exception.status_code, 404)

        alice.is_suspended = True
        self.db.commit()
        bob = self.make_user("targetfollowbob")
        with self.assertRaises(HTTPException) as follower_error:
            follow_routes.follow_user(bob.id, db=self.db, current_user=alice)
        self.assertEqual(follower_error.exception.status_code, 403)

    def test_users_directory_filters_metrics_and_sorting(self):
        viewer = self.make_user("dirviewer")
        friend = self.make_user("dirfriend")
        outgoing = self.make_user("diroutgoing")
        incoming = self.make_user("dirincoming")
        unrelated = self.make_user("dirunrelated")
        suspended = self.make_user("dirsuspended")
        suspended.is_suspended = True

        friend_first = self.make_post(friend, "Friend First")
        friend_first.view_count = 4
        friend_second = self.make_post(friend, "Friend Second")
        friend_second.view_count = 3
        friend_pending = self.make_post(friend, "Friend Pending", moderation_status="pending")
        friend_pending.view_count = 100
        outgoing_post = self.make_post(outgoing, "Outgoing Text")
        outgoing_post.view_count = 20
        self.db.add_all([
            models.Comment(post_id=friend_first.id, user_id=viewer.id, content="approved", approved=True, moderation_status="approved"),
            models.Comment(post_id=friend_first.id, user_id=viewer.id, content="pending", approved=False, moderation_status="pending"),
            models.Comment(post_id=friend_pending.id, user_id=viewer.id, content="hidden", approved=True, moderation_status="approved"),
        ])
        self.db.commit()

        sent = friend_routes.send_friend_request(friend.id, db=self.db, current_user=viewer)
        friend_routes.accept_friend_request(sent["friendship"]["id"], db=self.db, current_user=friend)
        friend_routes.send_friend_request(outgoing.id, db=self.db, current_user=viewer)
        friend_routes.send_friend_request(viewer.id, db=self.db, current_user=incoming)
        follow_routes.follow_user(outgoing.id, db=self.db, current_user=viewer)
        follow_routes.follow_user(viewer.id, db=self.db, current_user=incoming)

        payload = user_routes.list_users_directory(sort="posts", db=self.db, current_user=viewer)
        usernames = [item["username"] for item in payload["users"]]
        self.assertNotIn(viewer.username, usernames)
        self.assertNotIn(suspended.username, usernames)
        self.assertEqual(payload["total"], 4)
        self.assertEqual(payload["users"][0]["username"], friend.username)
        friend_payload = next(item for item in payload["users"] if item["username"] == friend.username)
        self.assertEqual(friend_payload["approved_post_count"], 2)
        self.assertEqual(friend_payload["total_view_count"], 7)
        self.assertEqual(friend_payload["approved_comment_count"], 1)
        self.assertEqual(friend_payload["friendship_status"], "friends")

        views_payload = user_routes.list_users_directory(sort="views", db=self.db, current_user=viewer)
        self.assertEqual(views_payload["users"][0]["username"], outgoing.username)
        comments_payload = user_routes.list_users_directory(sort="comments", db=self.db, current_user=viewer)
        self.assertEqual(comments_payload["users"][0]["username"], friend.username)
        followers_payload = user_routes.list_users_directory(sort="followers", db=self.db, current_user=viewer)
        self.assertEqual(followers_payload["users"][0]["username"], outgoing.username)

        self.assertEqual(
            [item["username"] for item in user_routes.list_users_directory(relationship="friends", db=self.db, current_user=viewer)["users"]],
            [friend.username],
        )
        self.assertEqual(
            [item["username"] for item in user_routes.list_users_directory(relationship="outgoing_pending", db=self.db, current_user=viewer)["users"]],
            [outgoing.username],
        )
        self.assertEqual(
            [item["username"] for item in user_routes.list_users_directory(relationship="incoming_pending", db=self.db, current_user=viewer)["users"]],
            [incoming.username],
        )
        self.assertEqual(
            [item["username"] for item in user_routes.list_users_directory(relationship="following", db=self.db, current_user=viewer)["users"]],
            [outgoing.username],
        )
        self.assertEqual(
            [item["username"] for item in user_routes.list_users_directory(relationship="followers", db=self.db, current_user=viewer)["users"]],
            [incoming.username],
        )
        self.assertEqual(
            [item["username"] for item in user_routes.list_users_directory(relationship="not_friends", db=self.db, current_user=viewer)["users"]],
            [unrelated.username],
        )
        self.assertEqual(
            [item["username"] for item in user_routes.list_users_directory(q="outgo", db=self.db, current_user=viewer)["users"]],
            [outgoing.username],
        )

        page = user_routes.list_users_directory(limit=2, db=self.db, current_user=viewer)
        self.assertEqual(len(page["users"]), 2)
        self.assertTrue(page["has_more"])

    def test_friend_request_blocks_self_and_suspended_targets(self):
        alice = self.make_user("blockalice")
        suspended = self.make_user("suspendedfriend")
        suspended.is_suspended = True
        self.db.commit()

        with self.assertRaises(HTTPException) as self_error:
            friend_routes.send_friend_request(alice.id, db=self.db, current_user=alice)
        self.assertEqual(self_error.exception.status_code, 400)

        with self.assertRaises(HTTPException) as suspended_error:
            friend_routes.send_friend_request(suspended.id, db=self.db, current_user=alice)
        self.assertEqual(suspended_error.exception.status_code, 404)

    def test_statistics_uses_configured_session_cookie(self):
        current_cookie = SimpleNamespace(cookies={"calimara_sess": "session-token"})
        old_cookie = SimpleNamespace(cookies={"session": "session-token"})

        fingerprint = statistics._get_session_fingerprint(current_cookie)

        self.assertIsNotNone(fingerprint)
        self.assertEqual(len(fingerprint), 32)
        self.assertIsNone(statistics._get_session_fingerprint(old_cookie))

    def test_moderation_log_ai_details_remain_json_object(self):
        user = self.make_user("moderated")
        result = moderation.ModerationResult(
            moderation.ModerationStatus.FLAGGED,
            0.7,
            "needs review",
            {
                "hate_and_discrimination": 0.7,
                "dangerous_and_criminal_content": 0.1,
                "romanian_signals": {"profanity_score": 0.2},
                "nested": {"ok": True},
            },
        )

        moderation.log_moderation_decision(self.db, "post", 123, user.id, result)
        self.db.commit()

        log_entry = self.db.query(models.ModerationLog).one()
        self.assertIsInstance(log_entry.ai_details, dict)
        self.assertTrue(log_entry.ai_details["nested"]["ok"])

    def test_post_reports_are_deduped_and_hidden_posts_cannot_be_reported(self):
        owner = self.make_user("reportowner")
        reporter = self.make_user("reportreader")
        post = self.make_post(owner, "Reportable Text")

        report_post = post_routes.report_post_api.__wrapped__
        created = report_post(
            post.id,
            schemas.PostReportCreate(
                reason_type="plagiarism",
                details="Text copiat",
                evidence_url="https://example.com/source",
            ),
            DummyRequest({}),
            db=self.db,
            current_user=reporter,
        )

        self.assertEqual(created["post_id"], post.id)
        self.assertEqual(created["reason_type"], "plagiarism")
        self.assertEqual(created["status"], "open")
        self.assertEqual(created["reporter_username"], "reportreader")

        with self.assertRaises(HTTPException) as duplicate:
            report_post(
                post.id,
                schemas.PostReportCreate(reason_type="plagiarism"),
                DummyRequest({}),
                db=self.db,
                current_user=reporter,
            )
        self.assertEqual(duplicate.exception.status_code, 409)

        pending = self.make_post(owner, "Pending Report Text", moderation_status="pending")
        with self.assertRaises(HTTPException) as pending_error:
            report_post(
                pending.id,
                schemas.PostReportCreate(reason_type="offensive"),
                DummyRequest({}),
                db=self.db,
                current_user=reporter,
            )
        self.assertEqual(pending_error.exception.status_code, 400)

    def test_moderators_can_review_post_reports(self):
        owner = self.make_user("reportedowner")
        reporter = self.make_user("reportedreader")
        moderator_user = self.make_user("reportmod")
        moderator_user.is_moderator = True
        self.db.commit()
        self.db.refresh(moderator_user)

        dismiss_post = self.make_post(owner, "Dismissed Report Text")
        reject_post = self.make_post(owner, "Rejected Report Text")
        delete_post = self.make_post(owner, "Deleted Report Text")

        dismiss_report = crud.create_post_report(
            self.db,
            post=dismiss_post,
            reporter_user_id=reporter.id,
            report=schemas.PostReportCreate(reason_type="offensive", details="Nu pare ok"),
        )
        reject_report = crud.create_post_report(
            self.db,
            post=reject_post,
            reporter_user_id=reporter.id,
            report=schemas.PostReportCreate(reason_type="plagiarism", evidence_url="https://example.com/original"),
        )
        delete_report = crud.create_post_report(
            self.db,
            post=delete_post,
            reporter_user_id=reporter.id,
            report=schemas.PostReportCreate(reason_type="offensive"),
        )

        listed = moderation_routes.get_post_reports(
            status_filter="open",
            limit=50,
            offset=0,
            db=self.db,
            current_user=moderator_user,
        )
        self.assertEqual({item["id"] for item in listed["reports"]}, {dismiss_report.id, reject_report.id, delete_report.id})

        dismissed = moderation_routes.review_post_report(
            dismiss_report.id,
            schemas.PostReportReview(action="dismiss", reason="Nu confirmă problema"),
            DummyRequest({}),
            db=self.db,
            current_user=moderator_user,
        )
        self.assertEqual(dismissed["report"]["status"], "dismissed")
        self.assertEqual(dismissed["report"]["reviewer_username"], "reportmod")

        rejected = moderation_routes.review_post_report(
            reject_report.id,
            schemas.PostReportReview(action="reject_post", reason="Plagiat confirmat"),
            DummyRequest({}),
            db=self.db,
            current_user=moderator_user,
        )
        self.db.refresh(reject_post)
        self.assertEqual(rejected["report"]["status"], "resolved")
        self.assertEqual(reject_post.moderation_status, "rejected")
        self.assertEqual(reject_post.moderation_reason, "Plagiat confirmat")

        deleted = moderation_routes.review_post_report(
            delete_report.id,
            schemas.PostReportReview(action="delete_post", reason="Șters după raportare"),
            DummyRequest({}),
            db=self.db,
            current_user=moderator_user,
        )
        self.assertEqual(deleted["report"]["status"], "resolved")
        self.assertIsNone(deleted["report"]["post_id"])
        self.assertIsNone(self.db.query(models.Post).filter(models.Post.id == delete_post.id).first())

    def test_run_init_database_can_preserve_existing_schema_without_migrations(self):
        import run

        executed_sql = []

        class FakeResult:
            def __init__(self, *, exists=False, scalar_value=None):
                self.exists = exists
                self.scalar_value = scalar_value

            def first(self):
                return object() if self.exists else None

            def scalar(self):
                return self.scalar_value

        class FakeConnection:
            def execute(self, statement, params=None):
                sql = str(statement)
                executed_sql.append(sql)
                if "FROM pg_database" in sql:
                    return FakeResult(exists=True)
                if "to_regclass" in sql:
                    return FakeResult(scalar_value="users")
                return FakeResult()

        class FakeConnect:
            def __enter__(self):
                return FakeConnection()

            def __exit__(self, exc_type, exc, traceback):
                return False

        class FakeEngine:
            def connect(self):
                return FakeConnect()

            def dispose(self):
                pass

        with patch.dict(os.environ, {"CALIMARA_RESET_DATABASE": "false"}), patch(
            "sqlalchemy.create_engine",
            return_value=FakeEngine(),
        ):
            run.init_database()

        self.assertTrue(any("FROM pg_database" in sql for sql in executed_sql))
        self.assertTrue(any("to_regclass" in sql for sql in executed_sql))
        self.assertFalse(any("ADD COLUMN" in sql for sql in executed_sql))
        self.assertFalse(any("CREATE TABLE" in sql for sql in executed_sql))
        self.assertFalse(any("DROP DATABASE" in sql for sql in executed_sql))
        self.assertFalse(any("CREATE DATABASE" in sql for sql in executed_sql))

    def test_run_init_database_resets_existing_schema_by_default(self):
        import run

        executed_sql = []

        class FakeResult:
            def __init__(self, *, exists=False):
                self.exists = exists

            def first(self):
                return object() if self.exists else None

        class FakeConnection:
            def execute(self, statement, params=None):
                sql = str(statement)
                executed_sql.append(sql)
                if "FROM pg_database" in sql:
                    return FakeResult(exists=True)
                return FakeResult()

            def commit(self):
                executed_sql.append("COMMIT")

        class FakeConnect:
            def __enter__(self):
                return FakeConnection()

            def __exit__(self, exc_type, exc, traceback):
                return False

        class FakeEngine:
            def connect(self):
                return FakeConnect()

            def dispose(self):
                pass

        with tempfile.TemporaryDirectory() as temp_dir:
            schema_file = Path(temp_dir) / "schema.sql"
            schema_file.write_text("CREATE TABLE users (id INT);\n", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=False), patch(
                "sqlalchemy.create_engine",
                return_value=FakeEngine(),
            ), patch.object(run, "SCHEMA_FILE", schema_file), patch(
                "scripts.seed.main"
            ), patch.object(
                run, "seed_dev_premium_user"
            ), patch.object(
                run, "verify_seed_data"
            ):
                os.environ.pop("CALIMARA_RESET_DATABASE", None)
                run.init_database()

        self.assertTrue(any("FROM pg_database" in sql for sql in executed_sql))
        self.assertTrue(any("DROP DATABASE" in sql for sql in executed_sql))
        self.assertTrue(any("CREATE DATABASE" in sql for sql in executed_sql))
        self.assertTrue(any("CREATE TABLE users" in sql for sql in executed_sql))

    def test_admin_routes_tolerate_missing_optional_admin_tables(self):
        admin_user = self.make_user("missingadmintables")
        admin_user.is_admin = True
        admin_user.is_moderator = True
        self.db.commit()
        self.db.refresh(admin_user)
        self.make_post(admin_user, "Admin Visible Post")

        with self.engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE admin_daily_metrics")
            connection.exec_driver_sql("DROP TABLE admin_audit_logs")

        overview = admin_routes.admin_overview(
            Response(),
            db=self.db,
            current_user=admin_user,
            from_date=None,
            to_date=None,
        )
        self.assertEqual(overview["daily_metrics"], [])
        self.assertGreaterEqual(overview["cards"]["total_users"], 1)

        audit_log = admin_routes.list_admin_audit_log(
            limit=100,
            offset=0,
            db=self.db,
            current_user=admin_user,
        )
        self.assertEqual(audit_log["logs"], [])
        self.assertTrue(audit_log["unavailable"])

        detail = admin_routes.get_admin_user_detail(
            admin_user.id,
            db=self.db,
            current_user=admin_user,
        )
        self.assertEqual(detail["audit"], [])

        rollup = admin_routes.rollup_admin_metrics(
            request=None,
            target_date=None,
            db=self.db,
            current_user=admin_user,
        )
        self.assertFalse(rollup["persisted"])
        self.assertEqual(rollup["date"], (datetime.now().date() - timedelta(days=1)).isoformat())

    def test_site_feedback_submission_and_admin_status_workflow(self):
        user = self.make_user("feedbackuser")
        admin_user = self.make_user("feedbackadmin")
        admin_user.is_admin = True
        admin_user.is_moderator = True
        self.db.commit()
        self.db.refresh(admin_user)

        created = user_routes.create_site_feedback(
            DummyRequest({}, headers={"user-agent": "pytest-browser"}),
            schemas.SiteFeedbackCreate(
                kind="bug",
                message="  Butonul nu răspunde  ",
                page_url="https://calimara.test/panou",
                client_context={"viewport": "1280x720"},
            ),
            db=self.db,
            current_user=user,
        )

        self.assertEqual(created["kind"], "bug")
        self.assertEqual(created["message"], "Butonul nu răspunde")
        self.assertEqual(created["status"], "open")
        self.assertEqual(created["username_snapshot"], "feedbackuser")

        listed = admin_routes.list_site_feedback(
            kind="all",
            status_filter="open",
            limit=50,
            offset=0,
            db=self.db,
            current_user=admin_user,
        )
        self.assertEqual(listed["total"], 1)
        self.assertEqual(listed["submissions"][0]["id"], created["id"])

        updated = admin_routes.update_site_feedback(
            created["id"],
            schemas.SiteFeedbackUpdate(status="closed", admin_note="Rezolvat în test"),
            DummyRequest({}, headers={"user-agent": "pytest-admin"}),
            db=self.db,
            current_user=admin_user,
        )
        self.assertEqual(updated["status"], "closed")
        self.assertEqual(updated["admin_note"], "Rezolvat în test")
        self.assertEqual(updated["resolver_username"], "feedbackadmin")

    def test_get_current_user_uses_id_lookup_and_clears_missing_sessions(self):
        user = self.make_user("alice")
        db_epoch = auth.get_db_epoch()

        current_user = auth.get_current_user(
            DummyRequest({"user_id": user.id, "db_epoch": db_epoch}),
            self.db,
        )
        self.assertIsNotNone(current_user)
        self.assertEqual(current_user.id, user.id)

        missing_request = DummyRequest({"user_id": 999_999, "db_epoch": db_epoch})
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
                "cover_seed": "cover-google",
            },
        )

        self.assertEqual(created_user.username, "googleuser")
        self.assertEqual(created_user.cover_seed, "cover-google")
        self.assertEqual(crud.get_user_by_id(self.db, created_user.id).email, "google@example.com")

        alias_payload = schemas.MessageToUser.model_validate({"username": "reader", "content": "Salut"})
        canonical_payload = schemas.MessageToUser.model_validate(
            {"recipient_username": "reader", "content": "Salut"}
        )
        profile_update = schemas.UserProfileUpdate.model_validate({"avatar_seed": "new-seed", "cover_seed": "new-cover"})

        self.assertEqual(alias_payload.recipient_username, "reader")
        self.assertEqual(canonical_payload.recipient_username, "reader")
        self.assertEqual(profile_update.avatar_seed, "new-seed")
        self.assertEqual(profile_update.cover_seed, "new-cover")
        self.assertIsNone(profile_update.subtitle)

    def test_auth_setup_persists_cover_seed(self):
        request = DummyRequest(
            {
                "google_user": {
                    "google_id": "google-cover-user",
                    "email": "coveruser@example.com",
                    "name": "Cover User",
                }
            }
        )
        payload = schemas.UserSetup.model_validate(
            {
                "username": "coveruser",
                "subtitle": "setup",
                "avatar_seed": "coveruser-shapes",
                "cover_seed": "coveruser-cover-forest",
            }
        )

        response = auth_routes.complete_user_setup(request, payload, self.db)
        created = crud.get_user_by_username(self.db, "coveruser")

        self.assertEqual(response["username"], "coveruser")
        self.assertEqual(created.cover_seed, "coveruser-cover-forest")
        self.assertEqual(request.session["user_id"], created.id)

    def test_password_signup_requires_activation_code_before_setup(self):
        request = DummyRequest({})
        with patch.dict(os.environ, {"EMAILS_ENABLED": "True"}), patch.object(
            auth_routes.email_service,
            "_send_with_brevo",
            return_value="message-id-activation",
        ) as send_mock, patch.object(auth_routes.local_auth, "generate_email_code", return_value="12345678"):
            response = auth_routes.register_with_password.__wrapped__(
                request,
                schemas.PasswordRegisterRequest(email="NewAuthor@Example.com", password="long-enough-password"),
                self.db,
            )

        self.assertEqual(response["email"], "newauthor@example.com")
        email_row = self.db.query(models.EmailOutbox).one()
        self.assertEqual(email_row.email_type, "auth")
        self.assertEqual(email_row.status, "sent")
        self.assertEqual(email_row.provider_message_id, "message-id-activation")
        self.assertIn("12345678", email_row.text_content)
        send_mock.assert_called_once()

        activation = auth_routes.activate_password_signup.__wrapped__(
            request,
            schemas.AuthCodeVerifyRequest(email="newauthor@example.com", code="12345678"),
            self.db,
        )
        self.assertIn("/autentificare/configurare", activation["setup_url"])
        self.assertEqual(request.session["pending_auth"]["source"], "password")

        setup_response = auth_routes.complete_user_setup(
            request,
            schemas.UserSetup(
                username="parolauser",
                subtitle="setup",
                avatar_seed="parolauser-shapes",
                cover_seed="parolauser-cover-sky",
            ),
            self.db,
        )
        created = crud.get_user_by_username(self.db, "parolauser")

        self.assertEqual(setup_response["username"], "parolauser")
        self.assertEqual(created.email, "newauthor@example.com")
        self.assertIsNone(created.google_id)
        self.assertIsNotNone(created.password_hash)
        self.assertIsNotNone(created.email_verified_at)
        self.assertTrue(local_auth.verify_password("long-enough-password", created.password_hash))
        self.assertEqual(request.session["user_id"], created.id)

    def test_password_login_uses_safe_return_target(self):
        user = self.make_user("passwordlogin")
        user.password_hash = local_auth.password_hash("long-enough-password")
        user.email_verified_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(user)
        self.db.commit()
        request = DummyRequest({})

        with patch.dict(
            os.environ,
            {"GOOGLE_REDIRECT_URI": "http://lvh.me:8000/auth/google/callback"},
        ), patch.object(auth_routes, "MAIN_DOMAIN", "lvh.me:8000"):
            response = auth_routes.login_with_password.__wrapped__(
                request,
                schemas.PasswordLoginRequest(
                    email=user.email,
                    password="long-enough-password",
                    return_to="/?post=42",
                ),
                self.db,
            )

        self.assertEqual(response["redirect_url"], "http://lvh.me:8000/?post=42")
        self.assertEqual(request.session["user_id"], user.id)

    def test_password_login_accepts_configured_frontend_port_return_target(self):
        user = self.make_user("passwordloginport")
        user.password_hash = local_auth.password_hash("long-enough-password")
        user.email_verified_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(user)
        self.db.commit()
        request = DummyRequest({})

        with patch.dict(
            os.environ,
            {"GOOGLE_REDIRECT_URI": "http://localhost:18173/auth/google/callback"},
        ), patch.object(auth_routes, "MAIN_DOMAIN", "localhost"), patch.object(auth_routes, "SUBDOMAIN_SUFFIX", ".localhost"):
            response = auth_routes.login_with_password.__wrapped__(
                request,
                schemas.PasswordLoginRequest(
                    email=user.email,
                    password="long-enough-password",
                    return_to="http://localhost:18173/",
                ),
                self.db,
            )

        self.assertEqual(response["redirect_url"], "http://localhost:18173/")
        self.assertEqual(request.session["user_id"], user.id)

    def test_password_reset_sets_password_for_existing_social_account(self):
        user = self.make_user("socialonly")
        user.email_verified_at = None
        self.db.add(user)
        self.db.commit()
        request = DummyRequest({})

        with patch.dict(os.environ, {"EMAILS_ENABLED": "True"}), patch.object(
            auth_routes.email_service,
            "_send_with_brevo",
            return_value="message-id-reset",
        ) as send_mock, patch.object(auth_routes.local_auth, "generate_email_code", return_value="87654321"):
            response = auth_routes.request_password_reset.__wrapped__(
                request,
                schemas.PasswordResetRequest(email=user.email),
                self.db,
            )

        self.assertEqual(response["next"], "reset_code")
        email_row = self.db.query(models.EmailOutbox).one()
        self.assertEqual(email_row.status, "sent")
        self.assertEqual(email_row.provider_message_id, "message-id-reset")
        self.assertIn("87654321", email_row.text_content)
        send_mock.assert_called_once()

        reset = auth_routes.confirm_password_reset.__wrapped__(
            request,
            schemas.PasswordResetConfirmRequest(
                email=user.email,
                code="87654321",
                password="new-long-password",
            ),
            self.db,
        )
        self.db.refresh(user)

        self.assertEqual(reset["username"], user.username)
        self.assertEqual(request.session["user_id"], user.id)
        self.assertIsNotNone(user.email_verified_at)
        self.assertTrue(local_auth.verify_password("new-long-password", user.password_hash))

    def test_facebook_callback_links_verified_email_to_existing_user(self):
        user = self.make_user("facebooklink")
        facebook_user = schemas.FacebookUserInfo(
            facebook_id="fb-123",
            email=user.email,
            name="Facebook Link",
            email_verified=True,
        )
        request = DummyRequest({})

        with patch.object(auth_routes.facebook_oauth, "handle_facebook_callback", new=AsyncMock(return_value=facebook_user)):
            response = self.async_run(auth_routes.facebook_callback.__wrapped__(request, self.db))

        self.db.refresh(user)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(user.facebook_id, "fb-123")
        self.assertEqual(request.session["user_id"], user.id)

    def test_facebook_callback_sends_new_users_to_generic_setup(self):
        facebook_user = schemas.FacebookUserInfo(
            facebook_id="fb-new",
            email="fbnew@example.com",
            name="Facebook New",
            email_verified=True,
        )
        request = DummyRequest({"user_id": 123})

        with patch.dict(os.environ, {"GOOGLE_REDIRECT_URI": "http://lvh.me:8000/auth/google/callback"}), patch.object(
            auth_routes,
            "MAIN_DOMAIN",
            "lvh.me:8000",
        ), patch.object(
            auth_routes.facebook_oauth,
            "handle_facebook_callback",
            new=AsyncMock(return_value=facebook_user),
        ):
            response = self.async_run(auth_routes.facebook_callback.__wrapped__(request, self.db))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "http://lvh.me:8000/autentificare/configurare")
        self.assertNotIn("user_id", request.session)
        self.assertEqual(request.session["pending_auth"]["source"], "facebook")
        self.assertEqual(request.session["pending_auth"]["provider_user"]["email"], "fbnew@example.com")

    def test_profile_settings_update_links_location_and_donations(self):
        user = self.make_user("profilelinks")
        payload = schemas.UserProfileSettingsUpdate.model_validate(
            {
                "location": "Iași",
                "cover_seed": "profilelinks-cover-garden",
                "youtube_playlist_url": "https://www.youtube.com/playlist?list=PL123",
                "paypal_url": "https://paypal.me/profilelinks",
                "patreon_url": "https://patreon.com/profilelinks",
                "instagram_url": "https://instagram.com/profilelinks",
            }
        )

        response = user_routes.update_profile_settings(payload, db=self.db, current_user=user)

        self.assertEqual(response["location"], "Iași")
        self.assertEqual(response["cover_seed"], "profilelinks-cover-garden")
        self.assertIn("profilelinks-cover-garden", response["cover_url"])
        self.assertEqual(response["youtube_playlist_url"], "https://www.youtube.com/playlist?list=PL123")
        self.assertEqual(response["paypal_url"], "https://paypal.me/profilelinks")
        self.assertEqual(response["patreon_url"], "https://patreon.com/profilelinks")

        bad_payload = schemas.UserProfileSettingsUpdate.model_validate(
            {"paypal_url": "https://example.com/not-paypal"}
        )
        with self.assertRaises(HTTPException) as bad_url:
            user_routes.update_profile_settings(bad_payload, db=self.db, current_user=user)
        self.assertEqual(bad_url.exception.status_code, 422)

    def test_public_profile_media_urls_are_hidden_when_premium_expires(self):
        user = self.make_user("profilemedia")
        user.profile_photo_storage_key = "users/1/profil.webp"
        user.cover_photo_storage_key = "users/1/coperta.webp"
        user.premium_until = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        self.db.commit()

        expired_payload = api_pages.serialize_user(user)
        self.assertIsNone(expired_payload["profile_photo_url"])
        self.assertIsNone(expired_payload["cover_photo_url"])
        self.assertIn("profilemedia-cover-sky", expired_payload["cover_url"])
        self.assertTrue(expired_payload["has_profile_photo"])

        user.premium_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)
        self.db.commit()
        active_payload = api_pages.serialize_user(user)
        self.assertEqual(active_payload["profile_photo_url"], "/api/utilizatori/profilemedia/media/profil")
        self.assertEqual(active_payload["cover_photo_url"], "/api/utilizatori/profilemedia/media/coperta")
        self.assertEqual(active_payload["cover_url"], "/api/utilizatori/profilemedia/media/coperta")

    def test_public_inventory_returns_read_only_user_items(self):
        user = self.make_user("publicinventory")
        user.gologani_balance = 77
        item = models.ShopItem(
            slug="public-frame",
            name="Ramă publică",
            description="Vizibilă în inventarul public.",
            price=25,
            slot="frame",
            sort_order=1,
        )
        self.db.add(item)
        self.db.flush()
        self.db.add(models.UserInventoryItem(user_id=user.id, item_id=item.id))
        self.db.add(models.UserEquippedItem(user_id=user.id, item_id=item.id, slot=item.slot))
        self.db.commit()

        payload = api_pages.user_public_inventory("publicinventory", db=self.db)

        self.assertEqual(payload["owner"]["username"], "publicinventory")
        self.assertEqual(payload["owner"]["gologani_balance"], 77)
        self.assertEqual(len(payload["inventory"]), 1)
        self.assertEqual(len(payload["equipped"]), 1)
        self.assertEqual(payload["inventory"][0]["item"]["name"], "Ramă publică")
        self.assertTrue(payload["inventory"][0]["item"]["equipped"])

    def test_public_inventory_unknown_user_raises_404(self):
        with self.assertRaises(HTTPException) as missing:
            api_pages.user_public_inventory("missing-user", db=self.db)

        self.assertEqual(missing.exception.status_code, 404)

    def test_blog_all_works_returns_all_approved_posts_with_comment_counts(self):
        user = self.make_user("allworks")
        reader = self.make_user("allworksreader")
        first = self.make_post(user, "First public work", category="poezie")
        second = self.make_post(user, "Second public work", category="proza_scurta")
        self.make_post(user, "Hidden work", moderation_status="pending")
        self.db.add_all(
            [
                models.Comment(post_id=first.id, user_id=reader.id, content="approved", approved=True, moderation_status="approved"),
                models.Comment(post_id=first.id, user_id=reader.id, content="pending", approved=False, moderation_status="pending"),
                models.Like(post_id=second.id, user_id=reader.id),
                models.SuperLike(post_id=second.id, user_id=reader.id),
            ]
        )
        self.db.commit()

        payload = api_pages.blog_all_works_data("allworks", db=self.db, current_user=None)

        self.assertEqual(payload["blog_owner"]["username"], "allworks")
        self.assertEqual([post["title"] for post in payload["posts"]], ["Second public work", "First public work"])
        first_payload = next(post for post in payload["posts"] if post["id"] == first.id)
        second_payload = next(post for post in payload["posts"] if post["id"] == second.id)
        self.assertEqual(first_payload["comments_count"], 1)
        self.assertEqual(second_payload["likes_count"], 1)
        self.assertEqual(second_payload["super_likes_count"], 1)

    def test_landing_data_returns_requested_approved_post(self):
        user = self.make_user("landingtarget")
        first = self.make_post(user, "First Landing")
        second = self.make_post(user, "Second Landing")

        payload = api_pages.landing_data(
            DummyRequest({}),
            category="toate",
            post_id=second.id,
            db=self.db,
            current_user=None,
        )

        self.assertEqual(payload["random_posts"][0]["id"], second.id)
        self.assertNotEqual(payload["random_posts"][0]["id"], first.id)

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

    def test_google_login_stores_same_site_return_target(self):
        request = DummyRequest({})

        with patch.object(
            auth_routes.google_oauth,
            "get_google_auth_url",
            return_value="https://accounts.google.com/o/oauth2/auth?client_id=test",
        ), patch.object(
            auth_routes,
            "MAIN_DOMAIN",
            "lvh.me:8000",
        ), patch.object(
            auth_routes,
            "SUBDOMAIN_SUFFIX",
            ".lvh.me:8000",
        ):
            response = self.async_run(
                auth_routes.google_login.__wrapped__(
                    request,
                    return_to="http://writer.lvh.me:8000/post-title",
                )
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            request.session[auth_routes.AUTH_RETURN_TO_SESSION_KEY],
            "http://writer.lvh.me:8000/post-title",
        )

    def test_google_login_ignores_external_return_target(self):
        request = DummyRequest({})

        with patch.object(
            auth_routes.google_oauth,
            "get_google_auth_url",
            return_value="https://accounts.google.com/o/oauth2/auth?client_id=test",
        ), patch.object(
            auth_routes,
            "MAIN_DOMAIN",
            "lvh.me:8000",
        ), patch.object(
            auth_routes,
            "SUBDOMAIN_SUFFIX",
            ".lvh.me:8000",
        ):
            self.async_run(
                auth_routes.google_login.__wrapped__(
                    request,
                    return_to="https://example.test/steal",
                )
            )

        self.assertNotIn(auth_routes.AUTH_RETURN_TO_SESSION_KEY, request.session)

    def test_legacy_google_callback_route_remains_registered(self):
        routes = {
            (route.path, tuple(sorted(route.methods)))
            for route in auth_routes.router.routes
            if hasattr(route, "methods")
        }

        self.assertIn(("/auth/google/callback", ("GET",)), routes)

    def test_private_archive_includes_unapproved_owned_posts(self):
        user = self.make_user("author")
        other_user = self.make_user("other")
        approved = self.make_post(user, "Approved Text")
        pending = self.make_post(user, "Pending Text", moderation_status="pending")
        flagged = self.make_post(user, "Flagged Text", moderation_status="flagged")
        flagged.moderation_reason = "Needs moderator review"
        other_pending = self.make_post(other_user, "Other Pending", moderation_status="pending")
        self.db.commit()
        self.db.refresh(flagged)

        public_posts = crud.get_latest_posts_for_user(self.db, user.id, limit=10)
        self.assertEqual({post.id for post in public_posts}, {approved.id})

        archive = post_routes.get_posts_archive(db=self.db, current_user=user)
        archived_by_id = {post["id"]: post for post in archive["posts"]}

        self.assertEqual(archive["total"], 3)
        self.assertIn(approved.id, archived_by_id)
        self.assertIn(pending.id, archived_by_id)
        self.assertIn(flagged.id, archived_by_id)
        self.assertNotIn(other_pending.id, archived_by_id)
        self.assertEqual(archived_by_id[pending.id]["moderation_status"], "pending")
        self.assertEqual(archived_by_id[flagged.id]["moderation_status"], "flagged")
        self.assertEqual(archived_by_id[flagged.id]["moderation_reason"], "Needs moderator review")

        first_page = post_routes.get_posts_archive(limit=2, offset=0, db=self.db, current_user=user)
        second_page = post_routes.get_posts_archive(limit=2, offset=2, db=self.db, current_user=user)
        self.assertEqual(first_page["total"], 3)
        self.assertEqual(len(first_page["posts"]), 2)
        self.assertEqual(len(second_page["posts"]), 1)

        editable = post_routes.get_owned_post_for_edit(approved.id, db=self.db, current_user=user)
        self.assertEqual(editable.id, approved.id)
        with self.assertRaises(HTTPException) as other_edit:
            post_routes.get_owned_post_for_edit(approved.id, db=self.db, current_user=other_user)
        self.assertEqual(other_edit.exception.status_code, 404)

        months = post_routes.get_available_months(db=self.db, current_user=user)["months"]
        self.assertEqual(sum(month["post_count"] for month in months), 3)

    def test_post_drafts_are_private_and_editable(self):
        user = self.make_user("drafter")
        other_user = self.make_user("otherdrafter")

        draft = post_routes.create_post_draft_api(
            schemas.PostDraftSave(
                title="Ciornă",
                content="<p>Text în lucru</p>",
                explanatory_note="Nota ciornei",
                category="proza_scurta",
            ),
            db=self.db,
            current_user=user,
        )

        drafts = post_routes.list_post_drafts(db=self.db, current_user=user)["drafts"]
        self.assertEqual([item.id for item in drafts], [draft.id])
        self.assertEqual(draft.category, "proza_scurta")
        self.assertEqual(drafts[0].explanatory_note, "Nota ciornei")

        second_draft = crud.create_post_draft(
            self.db,
            schemas.PostDraftSave(title="Ciornă secundară", content="<p>Altă ciornă</p>", category="poezie"),
            user.id,
        )
        first_page = post_routes.list_post_drafts(limit=1, offset=0, db=self.db, current_user=user)
        second_page = post_routes.list_post_drafts(limit=1, offset=1, db=self.db, current_user=user)
        self.assertEqual(first_page["total"], 2)
        self.assertEqual(first_page["limit"], 1)
        self.assertEqual(second_page["offset"], 1)
        self.assertEqual({first_page["drafts"][0].id, second_page["drafts"][0].id}, {draft.id, second_draft.id})

        updated = post_routes.update_post_draft_api(
            draft.id,
            schemas.PostDraftSave(title="Ciornă revizuită", content="<p>Alt text</p>", explanatory_note="Nota revizuită", category="poezie"),
            db=self.db,
            current_user=user,
        )
        self.assertEqual(updated.title, "Ciornă revizuită")
        self.assertEqual(updated.category, "poezie")
        self.assertEqual(updated.explanatory_note, "Nota revizuită")

        with self.assertRaises(HTTPException) as other_error:
            post_routes.get_post_draft_api(draft.id, db=self.db, current_user=other_user)
        self.assertEqual(other_error.exception.status_code, 404)

        response = post_routes.delete_post_draft_api(draft.id, db=self.db, current_user=user)
        self.assertEqual(response.status_code, 204)
        self.assertIsNone(crud.get_post_draft(self.db, draft.id, user.id))

    def test_publishing_from_draft_deletes_only_owned_draft(self):
        user = self.make_user("publishdrafter")
        other_user = self.make_user("otherpublishdrafter")
        draft = crud.create_post_draft(
            self.db,
            schemas.PostDraftSave(title="Draft title", content="<p>Draft body</p>", explanatory_note="Nota publicată", category="poezie"),
            user.id,
        )
        other_draft = crud.create_post_draft(
            self.db,
            schemas.PostDraftSave(title="Other draft", content="<p>Other body</p>", category="poezie"),
            other_user.id,
        )

        create_post_callable = getattr(post_routes.create_post, "__wrapped__", post_routes.create_post)
        with patch.object(post_routes.ai_queue, "enqueue_post_publish_job") as enqueue:
            post = self.async_run(
                create_post_callable(
                    DummyRequest({}),
                    schemas.PostCreate(
                        title="Publicat din ciornă",
                        content="<p>Text publicat</p>",
                        explanatory_note="Nota publicată",
                        category="poezie",
                        draft_id=draft.id,
                    ),
                    self.db,
                    user,
                )
            )

        self.assertEqual(post.user_id, user.id)
        self.assertEqual(post.category, "poezie")
        self.assertEqual(post.explanatory_note, "Nota publicată")
        editable_post = post_routes.get_owned_post_for_edit(post.id, db=self.db, current_user=user)
        self.assertEqual(editable_post.explanatory_note, "Nota publicată")
        updated_post = post_routes.update_post_api(
            post.id,
            schemas.PostUpdate(
                title="Publicat din ciornă revizuit",
                content="<p>Text publicat revizuit</p>",
                explanatory_note="Nota schimbată",
                category="poezie",
            ),
            db=self.db,
            current_user=user,
        )
        self.assertEqual(updated_post.explanatory_note, "Nota schimbată")
        self.assertIsNone(crud.get_post_draft(self.db, draft.id, user.id))
        self.assertIsNotNone(crud.get_post_draft(self.db, other_draft.id, other_user.id))
        enqueue.assert_called_once()

    def test_landing_render_counts_returned_post_view_once_per_dedup_window(self):
        author = self.make_user("landingwriter")
        post = self.make_post(author, "Landing Poem", category="poezie")
        request = DummyRequest(
            {},
            headers={"user-agent": "Mozilla/5.0 Calimara landing test"},
            client_host="203.0.113.10",
        )

        with patch.object(statistics, "STATS_ENABLED", True), patch.object(
            api_pages.crud,
            "get_weighted_random_posts",
            return_value=[post],
        ):
            first_payload = api_pages.landing_data(
                request=request,
                category="toate",
                db=self.db,
                current_user=None,
            )

            second_payload = api_pages.landing_data(
                request=request,
                category="toate",
                db=self.db,
                current_user=None,
            )

        self.db.refresh(post)
        self.assertEqual(post.view_count, 1)
        self.assertEqual(first_payload["random_posts"][0]["view_count"], 1)
        self.assertEqual(first_payload["random_posts"][0]["vizualizari"], 1)
        self.assertEqual(second_payload["random_posts"][0]["view_count"], 1)
        self.assertEqual(second_payload["random_posts"][0]["vizualizari"], 1)

        post_views = (
            self.db.query(models.PageView)
            .filter(
                models.PageView.content_type == "post",
                models.PageView.content_id == post.id,
            )
            .order_by(models.PageView.id.asc())
            .all()
        )
        self.assertEqual(len(post_views), 2)
        self.assertFalse(post_views[0].is_duplicate)
        self.assertTrue(post_views[1].is_duplicate)

    def test_post_detail_counts_unique_views_by_ip(self):
        author = self.make_user("detailwriter")
        post = self.make_post(author, "Detail Poem", category="poezie")
        first_request = DummyRequest(
            {},
            headers={"user-agent": "Mozilla/5.0 Calimara detail test"},
            client_host="203.0.113.20",
        )
        duplicate_request = DummyRequest(
            {},
            headers={"user-agent": "Mozilla/5.0 Calimara detail test"},
            client_host="203.0.113.20",
        )
        different_ip_request = DummyRequest(
            {},
            headers={"user-agent": "Mozilla/5.0 Calimara detail test"},
            client_host="203.0.113.21",
        )

        with patch.object(statistics, "STATS_ENABLED", True):
            first_payload = api_pages.post_detail_data(
                request=first_request,
                username=author.username,
                slug=post.slug,
                db=self.db,
                current_user=None,
            )
            duplicate_payload = api_pages.post_detail_data(
                request=duplicate_request,
                username=author.username,
                slug=post.slug,
                db=self.db,
                current_user=None,
            )
            different_ip_payload = api_pages.post_detail_data(
                request=different_ip_request,
                username=author.username,
                slug=post.slug,
                db=self.db,
                current_user=None,
            )

        self.db.refresh(post)
        self.assertEqual(post.view_count, 2)
        self.assertEqual(first_payload["post"]["view_count"], 1)
        self.assertEqual(duplicate_payload["post"]["view_count"], 1)
        self.assertEqual(different_ip_payload["post"]["view_count"], 2)

        post_views = (
            self.db.query(models.PageView)
            .filter(
                models.PageView.content_type == "post",
                models.PageView.content_id == post.id,
            )
            .order_by(models.PageView.id.asc())
            .all()
        )
        self.assertEqual(len(post_views), 3)
        self.assertFalse(post_views[0].is_duplicate)
        self.assertTrue(post_views[1].is_duplicate)
        self.assertFalse(post_views[2].is_duplicate)

    def test_dev_seed_marks_gocandan_as_admin_and_moderator(self):
        import run

        captured = []

        class FakeConnection:
            def execute(self, statement, params):
                captured.append((str(statement), params))

        class FakeBegin:
            def __enter__(self):
                return FakeConnection()

            def __exit__(self, exc_type, exc, traceback):
                return False

        class FakeEngine:
            def begin(self):
                return FakeBegin()

            def dispose(self):
                pass

        with patch("sqlalchemy.create_engine", return_value=FakeEngine()):
            run.seed_dev_premium_user("postgresql://example")

        self.assertEqual(len(captured), 1)
        sql, params = captured[0]
        self.assertIn("is_admin", sql)
        self.assertIn("is_moderator", sql)
        self.assertIn("is_admin = TRUE", sql)
        self.assertIn("is_moderator = TRUE", sql)
        self.assertEqual(params["email"], "gocandan@gmail.com")

    def test_run_starts_ai_worker_loop(self):
        import run

        class FakeProcess:
            pid = 12345

        fake_process = FakeProcess()
        run.child_processes.clear()

        with patch.dict(os.environ, {"AI_WORKER_ENABLED": "true"}), patch.object(
            run.subprocess,
            "Popen",
            return_value=fake_process,
        ) as popen:
            proc = run.start_ai_worker()

        self.assertIs(proc, fake_process)
        args = popen.call_args.args[0]
        self.assertEqual(args, [run.sys.executable, str(run.PROJECT_ROOT / "scripts" / "process_ai_jobs.py"), "--loop"])
        self.assertEqual(popen.call_args.kwargs["cwd"], str(run.PROJECT_ROOT))
        self.assertIn(fake_process, run.child_processes)
        run.child_processes.clear()

    def test_ai_worker_loop_survives_iteration_errors(self):
        import scripts.process_ai_jobs as process_ai_jobs

        calls = []

        def fake_run_once(limit, worker_id):
            calls.append((limit, worker_id))
            if len(calls) == 1:
                raise RuntimeError("database warming up")
            raise KeyboardInterrupt()

        argv = ["process_ai_jobs.py", "--loop", "--limit", "7", "--sleep", "0.01"]
        with patch.object(process_ai_jobs.sys, "argv", argv), patch.object(
            process_ai_jobs.ai_queue, "worker_id", return_value="test-worker"
        ), patch.object(
            process_ai_jobs, "run_once", side_effect=fake_run_once
        ), patch.object(
            process_ai_jobs.time, "sleep"
        ) as sleep, patch.object(
            process_ai_jobs.traceback, "print_exc"
        ):
            result = process_ai_jobs.main()

        self.assertEqual(result, 0)
        self.assertEqual(calls, [(7, "test-worker"), (7, "test-worker")])
        sleep.assert_called_once_with(0.01)

    def test_two_pass_moderation_sends_flagged_text_to_llm_review(self):
        classifier_response = SimpleNamespace(
            results=[
                SimpleNamespace(
                    category_scores=SimpleNamespace(
                        sexual=0.0,
                        hate_and_discrimination=0.82,
                        violence_and_threats=0.0,
                        dangerous_and_criminal_content=0.0,
                        selfharm=0.0,
                        health=0.0,
                        financial=0.0,
                        law=0.0,
                        pii=0.0,
                        jailbreaking=0.0,
                    ),
                    categories=SimpleNamespace(
                        sexual=False,
                        hate_and_discrimination=True,
                        violence_and_threats=False,
                        dangerous_and_criminal_content=False,
                        selfharm=False,
                        health=False,
                        financial=False,
                        law=False,
                        pii=False,
                        jailbreaking=False,
                    ),
                )
            ]
        )
        chat_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"safe": true, "reason": "context literar legitim"}'
                    )
                )
            ]
        )
        fake_client = SimpleNamespace(
            classifiers=SimpleNamespace(moderate=AsyncMock(return_value=classifier_response)),
            chat=SimpleNamespace(complete=AsyncMock(return_value=chat_response)),
        )
        fake_client.classifiers.moderate = lambda **kwargs: classifier_response
        fake_client.chat.complete = lambda **kwargs: chat_response

        with patch.object(moderation, "MODERATION_ENABLED", True), patch.object(
            moderation,
            "client",
            fake_client,
        ):
            result = moderation.moderate_post("Titlu", "Text literar semnalizat de primul nivel.")

        self.assertEqual(result.status, moderation.ModerationStatus.APPROVED)
        self.assertEqual(result.toxicity_score, 0.82)
        self.assertIn("Pass 2", result.reason)
        self.assertIn("pass2_verdict", result.details)

    def test_two_pass_moderation_flags_when_llm_review_rejects(self):
        classifier_response = SimpleNamespace(
            results=[
                SimpleNamespace(
                    category_scores=SimpleNamespace(
                        sexual=0.0,
                        hate_and_discrimination=0.0,
                        violence_and_threats=0.9,
                        dangerous_and_criminal_content=0.0,
                        selfharm=0.0,
                        health=0.0,
                        financial=0.0,
                        law=0.0,
                        pii=0.0,
                        jailbreaking=0.0,
                    ),
                    categories=SimpleNamespace(
                        sexual=False,
                        hate_and_discrimination=False,
                        violence_and_threats=True,
                        dangerous_and_criminal_content=False,
                        selfharm=False,
                        health=False,
                        financial=False,
                        law=False,
                        pii=False,
                        jailbreaking=False,
                    ),
                )
            ]
        )
        chat_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"safe": false, "reason": "amenințare explicită"}'
                    )
                )
            ]
        )
        fake_client = SimpleNamespace(
            classifiers=SimpleNamespace(moderate=lambda **kwargs: classifier_response),
            chat=SimpleNamespace(complete=lambda **kwargs: chat_response),
        )

        with patch.object(moderation, "MODERATION_ENABLED", True), patch.object(
            moderation,
            "client",
            fake_client,
        ):
            result = moderation.moderate_post("Titlu", "Text respins de al doilea nivel.")

        self.assertEqual(result.status, moderation.ModerationStatus.FLAGGED)
        self.assertEqual(result.toxicity_score, 0.9)
        self.assertIn("manual review", result.reason)

    def test_moderation_reads_dict_classifier_response(self):
        classifier_response = SimpleNamespace(
            results=[
                SimpleNamespace(
                    category_scores={
                        "sexual": 0.0,
                        "hate_and_discrimination": 0.82,
                        "violence_and_threats": 0.0,
                        "dangerous": 0.0,
                        "criminal": 0.0,
                        "selfharm": 0.0,
                        "health": 0.0,
                        "financial": 0.0,
                        "law": 0.0,
                        "pii": 0.0,
                        "jailbreaking": 0.0,
                    },
                    categories={
                        "sexual": False,
                        "hate_and_discrimination": True,
                        "violence_and_threats": False,
                        "dangerous": False,
                        "criminal": False,
                        "selfharm": False,
                        "health": False,
                        "financial": False,
                        "law": False,
                        "pii": False,
                        "jailbreaking": False,
                    },
                )
            ]
        )
        chat_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"safe": true, "reason": "context literar legitim"}'
                    )
                )
            ]
        )
        fake_client = SimpleNamespace(
            classifiers=SimpleNamespace(moderate=lambda **kwargs: classifier_response),
            chat=SimpleNamespace(complete=lambda **kwargs: chat_response),
        )

        with patch.object(moderation, "MODERATION_ENABLED", True), patch.object(
            moderation,
            "client",
            fake_client,
        ):
            result = moderation.moderate_post("Titlu", "Text semnalizat de model.")

        self.assertEqual(result.status, moderation.ModerationStatus.APPROVED)
        self.assertEqual(result.toxicity_score, 0.82)
        self.assertIn("Pass 2", result.reason)

    def test_romanian_profanity_forces_manual_review_when_classifier_is_clean(self):
        classifier_response = SimpleNamespace(
            results=[
                SimpleNamespace(
                    category_scores={
                        "sexual": 0.0,
                        "hate_and_discrimination": 0.0,
                        "violence_and_threats": 0.0,
                        "dangerous": 0.0,
                        "criminal": 0.0,
                        "selfharm": 0.0,
                        "health": 0.0,
                        "financial": 0.0,
                        "law": 0.0,
                        "pii": 0.0,
                        "jailbreaking": 0.0,
                    },
                    categories={
                        "sexual": False,
                        "hate_and_discrimination": False,
                        "violence_and_threats": False,
                        "dangerous": False,
                        "criminal": False,
                        "selfharm": False,
                        "health": False,
                        "financial": False,
                        "law": False,
                        "pii": False,
                        "jailbreaking": False,
                    },
                )
            ]
        )
        fake_client = SimpleNamespace(
            classifiers=SimpleNamespace(moderate=lambda **kwargs: classifier_response),
            chat=SimpleNamespace(complete=lambda **kwargs: self.fail("LLM review should not publish local profanity")),
        )

        with patch.object(moderation, "MODERATION_ENABLED", True), patch.object(
            moderation,
            "client",
            fake_client,
        ):
            result = moderation.moderate_forum_thread("Titlu", "Ești un idiot prost.")

        self.assertEqual(result.status, moderation.ModerationStatus.FLAGGED)
        self.assertGreater(result.toxicity_score, 0.0)
        self.assertIn("Romanian profanity", result.reason)
        self.assertTrue(result.details["romanian_signals"]["profanity_detected"])

    def test_moderation_errors_fail_closed_to_manual_review(self):
        with patch.object(moderation, "MODERATION_ENABLED", True), patch.object(
            moderation,
            "client",
            object(),
        ), patch.object(
            moderation,
            "classify_content",
            side_effect=RuntimeError("provider down"),
        ):
            result = moderation.moderate_post("Titlu", "Text care nu poate fi verificat.")

        self.assertEqual(result.status, moderation.ModerationStatus.FLAGGED)
        self.assertEqual(result.toxicity_score, 0.0)
        self.assertIn("manual review", result.reason)

    def test_google_callback_redirect_uses_configured_local_scheme(self):
        user = self.make_user("oauthuser")
        request = DummyRequest({}, scheme="https")

        with patch.dict(
            os.environ,
            {"GOOGLE_REDIRECT_URI": "http://lvh.me:8000/auth/google/callback"},
        ), patch.object(
            auth_routes,
            "MAIN_DOMAIN",
            "lvh.me:8000",
        ), patch.object(
            auth_routes,
            "SUBDOMAIN_SUFFIX",
            ".lvh.me:8000",
        ), patch.object(
            auth_routes.google_oauth,
            "handle_google_callback",
            new=AsyncMock(return_value=SimpleNamespace(email=user.email)),
        ), patch.object(
            auth_routes.google_oauth,
            "find_or_create_user",
            return_value=(user, False),
        ):
            response = self.async_run(auth_routes.google_callback.__wrapped__(request, self.db))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["location"],
            "http://oauthuser.lvh.me:8000",
        )
        self.assertEqual(request.session["user_id"], user.id)

    def test_google_callback_failure_returns_to_landing_with_error_flag(self):
        request = DummyRequest({}, scheme="https")

        with patch.dict(
            os.environ,
            {"GOOGLE_REDIRECT_URI": "http://lvh.me:8000/auth/google/callback"},
        ), patch.object(
            auth_routes,
            "MAIN_DOMAIN",
            "lvh.me:8000",
        ), patch.object(
            auth_routes.google_oauth,
            "handle_google_callback",
            new=AsyncMock(side_effect=HTTPException(status_code=400, detail="bad oauth")),
        ):
            response = self.async_run(auth_routes.google_callback.__wrapped__(request, self.db))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "http://lvh.me:8000/?auth_error=google")
        self.assertNotIn("user_id", request.session)

    def test_google_callback_redirects_to_stored_return_target(self):
        user = self.make_user("oauthreturn")
        request = DummyRequest(
            {auth_routes.AUTH_RETURN_TO_SESSION_KEY: "http://lvh.me:8000/?post=42"},
            scheme="https",
        )

        with patch.dict(
            os.environ,
            {"GOOGLE_REDIRECT_URI": "http://lvh.me:8000/auth/google/callback"},
        ), patch.object(
            auth_routes,
            "MAIN_DOMAIN",
            "lvh.me:8000",
        ), patch.object(
            auth_routes,
            "SUBDOMAIN_SUFFIX",
            ".lvh.me:8000",
        ), patch.object(
            auth_routes.google_oauth,
            "handle_google_callback",
            new=AsyncMock(return_value=SimpleNamespace(email=user.email)),
        ), patch.object(
            auth_routes.google_oauth,
            "find_or_create_user",
            return_value=(user, False),
        ):
            response = self.async_run(auth_routes.google_callback.__wrapped__(request, self.db))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "http://lvh.me:8000/?post=42")
        self.assertEqual(request.session["user_id"], user.id)

    def test_google_callback_sends_new_users_to_setup_and_clears_stale_login(self):
        existing_user = self.make_user("olduser")
        request = DummyRequest({"user_id": existing_user.id, "db_epoch": "old"}, scheme="https")
        google_user = SimpleNamespace(
            google_id="google-new-user",
            email="newuser@example.com",
            name="New User",
            picture=None,
        )

        with patch.dict(
            os.environ,
            {"GOOGLE_REDIRECT_URI": "http://lvh.me:8000/auth/google/callback"},
        ), patch.object(
            auth_routes,
            "MAIN_DOMAIN",
            "lvh.me:8000",
        ), patch.object(
            auth_routes.google_oauth,
            "handle_google_callback",
            new=AsyncMock(return_value=google_user),
        ), patch.object(
            auth_routes.google_oauth,
            "find_or_create_user",
            return_value=(None, True),
        ):
            response = self.async_run(auth_routes.google_callback.__wrapped__(request, self.db))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["location"],
            "http://lvh.me:8000/autentificare/configurare",
        )
        self.assertNotIn("user_id", request.session)
        self.assertEqual(request.session["google_user"]["email"], "newuser@example.com")

    def test_react_entrypoint_responses_disable_browser_cache(self):
        from fastapi.testclient import TestClient
        from app.main import app as fastapi_app

        client = TestClient(fastapi_app)

        for path in ("/", "/scrie"):
            response = client.get(path, headers={"host": "lvh.me:8000"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(response.headers["pragma"], "no-cache")
            self.assertEqual(response.headers["expires"], "0")

    def test_docs_route_requires_admin(self):
        from fastapi.testclient import TestClient
        import app.main as main

        client = TestClient(main.app)

        anonymous = client.get("/docs", headers={"host": "lvh.me:8000"})
        self.assertEqual(anonymous.status_code, 401)

        non_admin = models.User(username="docsreader", email="docsreader@example.com", is_admin=False)
        main.app.dependency_overrides[auth.get_current_user] = lambda: non_admin
        try:
            forbidden = client.get("/docs", headers={"host": "lvh.me:8000"})
            self.assertEqual(forbidden.status_code, 403)
        finally:
            main.app.dependency_overrides.pop(auth.get_current_user, None)

        admin_user = models.User(username="docsadmin", email="docsadmin@example.com", is_admin=True)
        main.app.dependency_overrides[auth.get_current_user] = lambda: admin_user
        try:
            allowed = client.get("/docs", headers={"host": "lvh.me:8000"})
            self.assertIn(allowed.status_code, {200, 404})
        finally:
            main.app.dependency_overrides.pop(auth.get_current_user, None)

    def test_ads_txt_uses_configured_publisher_id(self):
        from fastapi.testclient import TestClient
        import app.main as main

        client = TestClient(main.app)

        with patch.object(main, "ADSENSE_PUBLISHER_ID", "pub-1234567890123456"):
            response = client.get("/ads.txt", headers={"host": "lvh.me:8000"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"].split(";")[0], "text/plain")
        self.assertEqual(
            response.text,
            "google.com, pub-1234567890123456, DIRECT, f08c47fec0942fa0\n",
        )

        with patch.object(main, "ADSENSE_PUBLISHER_ID", ""):
            disabled = client.get("/ads.txt", headers={"host": "lvh.me:8000"})

        self.assertEqual(disabled.status_code, 404)

    def test_auth_setup_spa_response_disables_browser_cache(self):
        response = auth_routes.auth_setup_page(DummyRequest({"google_user": {"email": "new@example.com"}}))

        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["pragma"], "no-cache")
        self.assertEqual(response.headers["expires"], "0")

    def test_theme_helpers_return_normalized_deduplicated_values(self):
        author = self.make_user("writer")
        self.make_post(
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

        self.assertEqual(crud.get_distinct_themes(self.db), ["dor", "timp"])
        self.assertEqual(crud.get_distinct_feelings(self.db), ["bucurie", "nostalgie"])

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

    def test_mentions_create_notifications_after_public_approval(self):
        author = self.make_user("mentionauthor")
        commenter = self.make_user("mentioncommenter")
        target = self.make_user("mentiontarget")
        other_target = self.make_user("mentionother")
        post = self.make_post(author, "Mention Post")

        self.assertEqual(
            crud.extract_mentioned_usernames("<p>@mentiontarget @mentiontarget a@ignored @MentionOther</p>"),
            ["mentiontarget", "MentionOther"],
        )
        linked = crud.link_mentions_in_rich_text(
            self.db,
            '<p>Salut @mentiontarget și @missing.</p><script>bad()</script>',
        )
        self.assertIn('href="//mentiontarget.calimara.ro"', linked)
        self.assertIn(">@mentiontarget</a>", linked)
        self.assertIn("@missing", linked)
        self.assertNotIn("<script", linked)

        comment = crud.create_comment(
            self.db,
            schemas.CommentCreate(content="<p>Salut @mentiontarget @mentiontarget și @mentioncommenter.</p>"),
            post_id=post.id,
            user_id=commenter.id,
        )
        self.assertEqual(crud.get_unread_notification_count(self.db, target.id), 0)
        crud.approve_comment(self.db, comment.id)
        self.assertEqual(crud.get_unread_notification_count(self.db, target.id), 1)
        self.assertEqual(crud.get_unread_notification_count(self.db, commenter.id), 0)
        comment_notification = crud.get_notifications_for_user(self.db, target.id)[0]
        self.assertEqual(comment_notification.type, "mention")
        self.assertEqual(comment_notification.extra_data["source_type"], "comment")
        self.assertIn(f"/{post.slug}#comment-{comment.id}", comment_notification.link)
        comment_payload = api_pages.serialize_comment(comment, self.db)
        self.assertIn('class="mention-link"', comment_payload["content"])
        self.assertIn('href="//mentiontarget.calimara.ro"', comment_payload["content"])

        approved = SimpleNamespace(
            status=moderation.ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason="ok",
        )
        thread = crud.create_forum_thread(
            self.db,
            author,
            schemas.ForumThreadCreate(
                section="general",
                title="Mentions in forum",
                content="Discuție pentru @mentiontarget și @mentionother.",
            ),
        )
        crud.apply_forum_thread_moderation_result(self.db, thread, approved)
        self.assertEqual(crud.get_unread_notification_count(self.db, target.id), 2)
        self.assertEqual(crud.get_unread_notification_count(self.db, other_target.id), 1)
        thread_payload = forum_routes._thread_detail_payload(self.db, thread, author)
        self.assertIn('href="//mentiontarget.calimara.ro"', thread_payload["content"])
        self.assertIn('href="//mentionother.calimara.ro"', thread_payload["content"])

        reply, error = crud.create_forum_reply(
            self.db,
            commenter,
            thread,
            schemas.ForumReplyCreate(content="Răspuns pentru @mentiontarget."),
        )
        self.assertIsNone(error)
        crud.apply_forum_reply_moderation_result(self.db, reply, approved)
        latest_target_notification = crud.get_notifications_for_user(self.db, target.id)[0]
        self.assertEqual(latest_target_notification.extra_data["source_type"], "forum_reply")
        self.assertEqual(latest_target_notification.link, f"/discutii/{thread.slug}#reply-{reply.id}")
        reply_payload = forum_routes._thread_detail_payload(self.db, thread, author)["replies"][0]
        self.assertIn('href="//mentiontarget.calimara.ro"', reply_payload["content"])

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

    def test_forum_crud_supports_thread_reply_lifecycle_and_permissions(self):
        alice = self.make_user("alice")
        bob = self.make_user("bob")
        carol = self.make_user("carol")
        moderator_user = self.make_user("moderator")
        moderator_user.is_moderator = True
        self.db.commit()

        approved = SimpleNamespace(
            status=moderation.ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason="ok",
        )

        thread = crud.create_forum_thread(
            self.db,
            alice,
            schemas.ForumThreadCreate(
                section="general",
                title="Atelier de metafore",
                content="Cum lucrăm cu metaforele fără să le forțăm?",
            ),
        )
        duplicate = crud.create_forum_thread(
            self.db,
            bob,
            schemas.ForumThreadCreate(
                section="general",
                title="Atelier de metafore",
                content="Altă discuție cu același titlu.",
            ),
        )

        self.assertEqual(thread.moderation_status, "pending")
        self.assertNotEqual(thread.slug, duplicate.slug)
        self.assertEqual(crud.list_forum_threads(self.db), [])

        crud.apply_forum_thread_moderation_result(self.db, thread, approved)
        visible_threads = crud.list_forum_threads(self.db)
        self.assertEqual([item.id for item in visible_threads], [thread.id])

        reply, error = crud.create_forum_reply(
            self.db,
            bob,
            thread,
            schemas.ForumReplyCreate(content="Aș porni de la imagine, nu de la explicație."),
        )
        self.assertIsNone(error)
        self.assertEqual(reply.moderation_status, "pending")
        self.assertEqual(crud.get_unread_notification_count(self.db, alice.id), 0)

        crud.apply_forum_reply_moderation_result(self.db, reply, approved)
        replies = crud.list_forum_replies_for_thread(self.db, thread.id, alice)
        self.assertEqual([item.id for item in replies], [reply.id])
        self.assertEqual(crud.get_unread_notification_count(self.db, alice.id), 1)

        updated, error = crud.update_forum_thread_state(self.db, alice, thread, "lock")
        self.assertIsNone(updated)
        self.assertEqual(error, "not_allowed")

        updated, error = crud.update_forum_thread_state(self.db, moderator_user, thread, "lock")
        self.assertIsNone(error)
        self.assertTrue(updated.is_locked)

        locked_reply, error = crud.create_forum_reply(
            self.db,
            bob,
            updated,
            schemas.ForumReplyCreate(content="Nu pot răspunde într-o discuție închisă."),
        )
        self.assertIsNone(locked_reply)
        self.assertEqual(error, "locked")

        self.assertFalse(crud.delete_forum_reply(self.db, carol, reply))
        self.assertTrue(crud.delete_forum_reply(self.db, bob, reply))
        self.assertEqual(self.db.query(models.ForumReply).count(), 0)

    def test_forum_content_integrates_with_moderation_helpers(self):
        alice = self.make_user("alice")
        bob = self.make_user("bob")
        moderator_user = self.make_user("moderator")
        moderator_user.is_moderator = True
        self.db.commit()

        flagged = SimpleNamespace(
            status=moderation.ModerationStatus.FLAGGED,
            toxicity_score=0.8,
            reason="needs review",
        )
        approved = SimpleNamespace(
            status=moderation.ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason="human approved",
        )

        thread = crud.create_forum_thread(
            self.db,
            alice,
            schemas.ForumThreadCreate(
                section="feedback",
                title="Critică pentru un fragment",
                content="Aș vrea feedback pe ritm de la @bob.",
            ),
        )
        crud.apply_forum_thread_moderation_result(self.db, thread, flagged)
        self.assertEqual(thread.moderation_status, "flagged")
        self.assertEqual(crud.get_moderation_stats(self.db)["forum_threads_flagged"], 1)

        crud.approve_content(self.db, "forum_thread", thread.id, moderator_user.id, "ok")
        self.db.refresh(thread)
        self.assertEqual(thread.moderation_status, "approved")
        self.assertEqual(crud.get_unread_notification_count(self.db, bob.id), 1)

        reply, error = crud.create_forum_reply(
            self.db,
            bob,
            thread,
            schemas.ForumReplyCreate(content="Fragmentul are un final puternic."),
        )
        self.assertIsNone(error)
        crud.apply_forum_reply_moderation_result(self.db, reply, flagged)
        self.assertEqual(reply.moderation_status, "flagged")

        crud.approve_content(self.db, "forum_reply", reply.id, moderator_user.id, "ok")
        self.db.refresh(reply)
        self.assertEqual(reply.moderation_status, "approved")
        self.assertEqual(crud.get_unread_notification_count(self.db, alice.id), 2)

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
