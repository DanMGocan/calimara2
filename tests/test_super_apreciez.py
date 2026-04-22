import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

from app import crud, models
from app.week_util import end_of_iso_week_utc, start_of_iso_week_utc, utcnow_naive


class SuperLikeModelTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        models.Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _make_user(self, username, premium=False):
        u = models.User(
            username=username,
            email=f"{username}@x.test",
            google_id=f"g-{username}",
        )
        if premium:
            u.premium_until = utcnow_naive() + timedelta(days=30)
        self.db.add(u)
        self.db.commit()
        self.db.refresh(u)
        return u

    def _make_post(self, user, title):
        p = models.Post(
            user_id=user.id,
            title=title,
            slug=f"{user.username}-{title}".lower(),
            content="c",
        )
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return p

    def test_super_like_can_be_created(self):
        alice = self._make_user("alice")
        bob = self._make_user("bob")
        post = self._make_post(alice, "p1")

        sl = models.SuperLike(post_id=post.id, user_id=bob.id)
        self.db.add(sl)
        self.db.commit()

        self.assertEqual(self.db.query(models.SuperLike).count(), 1)
        self.db.refresh(post)
        self.assertEqual(post.super_likes_count, 1)

    def test_super_like_unique_constraint_blocks_duplicates(self):
        alice = self._make_user("alice")
        bob = self._make_user("bob")
        post = self._make_post(alice, "p1")

        self.db.add(models.SuperLike(post_id=post.id, user_id=bob.id))
        self.db.commit()

        self.db.add(models.SuperLike(post_id=post.id, user_id=bob.id))
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_is_premium_property_reads_premium_until(self):
        alice = self._make_user("alice")
        self.assertFalse(alice.is_premium)

        alice.premium_until = utcnow_naive() + timedelta(days=10)
        self.db.commit()
        self.db.refresh(alice)
        self.assertTrue(alice.is_premium)

        alice.premium_until = utcnow_naive() - timedelta(minutes=1)
        self.db.commit()
        self.db.refresh(alice)
        self.assertFalse(alice.is_premium)


class WeekBoundaryTests(unittest.TestCase):
    def test_monday_midnight_utc_returns_same_instant(self):
        monday_0000 = datetime(2026, 4, 20, 0, 0, 0, tzinfo=timezone.utc)
        with patch("app.week_util._now", return_value=monday_0000):
            self.assertEqual(start_of_iso_week_utc(), monday_0000)

    def test_sunday_returns_previous_monday(self):
        sunday_2359 = datetime(2026, 4, 26, 23, 59, 59, tzinfo=timezone.utc)
        with patch("app.week_util._now", return_value=sunday_2359):
            self.assertEqual(
                start_of_iso_week_utc(),
                datetime(2026, 4, 20, 0, 0, 0, tzinfo=timezone.utc),
            )

    def test_end_of_week_is_next_monday_midnight(self):
        wednesday = datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)
        with patch("app.week_util._now", return_value=wednesday):
            self.assertEqual(
                end_of_iso_week_utc(),
                datetime(2026, 4, 27, 0, 0, 0, tzinfo=timezone.utc),
            )


class SuperLikeCrudTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        models.Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _user(self, name, premium=False):
        u = models.User(username=name, email=f"{name}@x.t", google_id=f"g-{name}")
        if premium:
            u.premium_until = utcnow_naive() + timedelta(days=30)
        self.db.add(u)
        self.db.commit()
        self.db.refresh(u)
        return u

    def _post(self, user, title):
        p = models.Post(user_id=user.id, title=title, slug=f"{user.username}-{title}", content="c")
        self.db.add(p); self.db.commit(); self.db.refresh(p); return p

    def test_create_super_like_happy_path(self):
        alice = self._user("alice"); bob = self._user("bob")
        post = self._post(alice, "p1")
        sl = crud.create_super_like(self.db, user=bob, post_id=post.id)
        self.assertIsNotNone(sl.id)
        self.db.refresh(post)
        self.assertEqual(post.super_likes_count, 1)

    def test_create_super_like_rejects_self(self):
        alice = self._user("alice"); post = self._post(alice, "p1")
        with self.assertRaises(crud.SuperLikeSelfError):
            crud.create_super_like(self.db, user=alice, post_id=post.id)

    def test_create_super_like_rejects_duplicate(self):
        alice = self._user("alice"); bob = self._user("bob"); post = self._post(alice, "p1")
        crud.create_super_like(self.db, user=bob, post_id=post.id)
        with self.assertRaises(crud.SuperLikeDuplicateError):
            crud.create_super_like(self.db, user=bob, post_id=post.id)

    def test_create_super_like_rejects_post_not_found(self):
        bob = self._user("bob")
        with self.assertRaises(crud.SuperLikePostNotFoundError):
            crud.create_super_like(self.db, user=bob, post_id=9999)

    def test_free_user_weekly_quota_one(self):
        alice = self._user("alice"); bob = self._user("bob")
        p1 = self._post(alice, "p1"); p2 = self._post(alice, "p2")
        crud.create_super_like(self.db, user=bob, post_id=p1.id)
        with self.assertRaises(crud.SuperLikeQuotaError):
            crud.create_super_like(self.db, user=bob, post_id=p2.id)

    def test_premium_user_weekly_quota_three(self):
        alice = self._user("alice"); bob = self._user("bob", premium=True)
        posts = [self._post(alice, f"p{i}") for i in range(4)]
        for p in posts[:3]:
            crud.create_super_like(self.db, user=bob, post_id=p.id)
        with self.assertRaises(crud.SuperLikeQuotaError):
            crud.create_super_like(self.db, user=bob, post_id=posts[3].id)

    def test_delete_super_like_removes_row(self):
        alice = self._user("alice"); bob = self._user("bob"); post = self._post(alice, "p1")
        crud.create_super_like(self.db, user=bob, post_id=post.id)
        self.assertTrue(crud.delete_super_like(self.db, user=bob, post_id=post.id))
        self.assertEqual(self.db.query(models.SuperLike).count(), 0)

    def test_delete_super_like_returns_false_when_absent(self):
        alice = self._user("alice"); bob = self._user("bob"); post = self._post(alice, "p1")
        self.assertFalse(crud.delete_super_like(self.db, user=bob, post_id=post.id))

    def test_get_user_weekly_count(self):
        alice = self._user("alice"); bob = self._user("bob")
        p1 = self._post(alice, "p1")
        crud.create_super_like(self.db, user=bob, post_id=p1.id)
        self.assertEqual(crud.get_user_weekly_super_like_count(self.db, bob.id), 1)

    def test_user_super_liked_post_check(self):
        alice = self._user("alice"); bob = self._user("bob"); post = self._post(alice, "p1")
        self.assertFalse(crud.user_super_liked_post(self.db, user_id=bob.id, post_id=post.id))
        crud.create_super_like(self.db, user=bob, post_id=post.id)
        self.assertTrue(crud.user_super_liked_post(self.db, user_id=bob.id, post_id=post.id))


class StripeUserCrudTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _user(self, name):
        u = models.User(username=name, email=f"{name}@x.t", google_id=f"g-{name}")
        self.db.add(u); self.db.commit(); self.db.refresh(u); return u

    def test_upsert_stripe_customer_id_sets_value(self):
        u = self._user("alice")
        crud.upsert_stripe_customer_id(self.db, user_id=u.id, customer_id="cus_123")
        self.db.refresh(u)
        self.assertEqual(u.stripe_customer_id, "cus_123")

    def test_get_user_by_stripe_customer_id_returns_user(self):
        u = self._user("alice")
        crud.upsert_stripe_customer_id(self.db, user_id=u.id, customer_id="cus_456")
        found = crud.get_user_by_stripe_customer_id(self.db, "cus_456")
        self.assertEqual(found.id, u.id)

    def test_set_premium_from_subscription_sets_fields(self):
        u = self._user("alice")
        expiry = utcnow_naive() + timedelta(days=30)
        crud.set_premium_from_subscription(
            self.db,
            user_id=u.id,
            subscription_id="sub_x",
            premium_until=expiry,
        )
        self.db.refresh(u)
        self.assertEqual(u.stripe_subscription_id, "sub_x")
        self.assertAlmostEqual(u.premium_until.timestamp(), expiry.timestamp(), delta=1)

    def test_clear_subscription_keeps_premium_until(self):
        u = self._user("alice")
        future = utcnow_naive() + timedelta(days=10)
        crud.set_premium_from_subscription(self.db, user_id=u.id, subscription_id="sub_x", premium_until=future)
        crud.clear_stripe_subscription(self.db, user_id=u.id)
        self.db.refresh(u)
        self.assertIsNone(u.stripe_subscription_id)
        self.assertIsNotNone(u.premium_until)

    def test_record_stripe_event_idempotent(self):
        self.assertTrue(crud.record_stripe_event(self.db, "evt_1", "customer.subscription.created"))
        self.assertFalse(crud.record_stripe_event(self.db, "evt_1", "customer.subscription.created"))


if __name__ == "__main__":
    unittest.main()
