import os
import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ["STRIPE_ENABLED"] = "True"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_dummy"
os.environ["STRIPE_PRICE_ID_PREMIUM_MONTHLY"] = "price_dummy"
os.environ["STRIPE_PRICE_ID_AUDIO_MONTHLY"] = "price_audio_dummy"
os.environ["STRIPE_PRICE_ID_AUTHOR_AUDIO_MONTHLY"] = "price_author_audio_dummy"
os.environ["STRIPE_SUCCESS_URL"] = "http://x/success"
os.environ["STRIPE_CANCEL_URL"] = "http://x/cancel"
os.environ["STRIPE_CUSTOMER_PORTAL_RETURN_URL"] = "http://x/panou"

from app import crud, models
from app.week_util import utcnow_naive


def _mk_event(event_id, event_type, customer_id="cus_1", sub_id="sub_1", period_end_ts=None, period_start_ts=None, tier="premium"):
    price_id = {
        "premium": "price_dummy",
        "audio": "price_audio_dummy",
        "author_audio": "price_author_audio_dummy",
    }.get(tier, "price_dummy")
    return {
        "id": event_id,
        "type": event_type,
        "data": {
            "object": {
                "id": sub_id,
                "customer": customer_id,
                "metadata": {"tier": tier},
                "items": {"data": [{"price": {"id": price_id}}]},
                "current_period_start": period_start_ts
                or int((utcnow_naive() - timedelta(hours=1)).timestamp()),
                "current_period_end": period_end_ts
                or int((utcnow_naive() + timedelta(days=30)).timestamp()),
            }
        },
    }


class WebhookIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.user = models.User(
            username="alice",
            email="a@x.t",
            google_id="g-a",
            stripe_customer_id="cus_1",
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_record_event_is_new_first_time(self):
        self.assertTrue(crud.record_stripe_event(self.db, "evt_1", "customer.subscription.created"))

    def test_record_event_is_no_op_second_time(self):
        crud.record_stripe_event(self.db, "evt_1", "customer.subscription.created")
        self.assertFalse(crud.record_stripe_event(self.db, "evt_1", "customer.subscription.created"))

    def test_process_subscription_updated_sets_premium_until(self):
        from app.routers.premium_routes import _apply_subscription_event

        ts = int((utcnow_naive() + timedelta(days=15)).timestamp())
        event = _mk_event("evt_2", "customer.subscription.updated", period_end_ts=ts)
        _apply_subscription_event(self.db, event)
        self.db.refresh(self.user)
        self.assertIsNotNone(self.user.premium_until)
        self.assertIsNotNone(self.user.premium_period_start)
        self.assertEqual(self.user.stripe_subscription_id, "sub_1")
        self.assertEqual(self.user.premium_tier, "premium")

    def test_process_audio_subscription_sets_audio_tier(self):
        from app.routers.premium_routes import _apply_subscription_event

        event = _mk_event("evt_audio", "customer.subscription.updated", tier="audio")
        _apply_subscription_event(self.db, event)
        self.db.refresh(self.user)
        self.assertEqual(self.user.premium_tier, "audio")
        self.assertTrue(self.user.has_audio_access)
        self.assertFalse(self.user.has_author_audio_access)

    def test_process_author_audio_subscription_sets_author_audio_tier(self):
        from app.routers.premium_routes import _apply_subscription_event

        event = _mk_event("evt_author_audio", "customer.subscription.updated", tier="author_audio")
        _apply_subscription_event(self.db, event)
        self.db.refresh(self.user)
        self.assertEqual(self.user.premium_tier, "author_audio")
        self.assertTrue(self.user.has_audio_access)
        self.assertTrue(self.user.has_author_audio_access)

    def test_process_subscription_deleted_clears_subscription_keeps_premium_until(self):
        from app.routers.premium_routes import _apply_subscription_event

        future = utcnow_naive() + timedelta(days=20)
        crud.set_premium_from_subscription(
            self.db, user_id=self.user.id, subscription_id="sub_1", premium_until=future
        )
        event = _mk_event("evt_3", "customer.subscription.deleted")
        _apply_subscription_event(self.db, event)
        self.db.refresh(self.user)
        self.assertIsNone(self.user.stripe_subscription_id)
        self.assertIsNotNone(self.user.premium_until)

    def test_unknown_customer_does_not_crash(self):
        from app.routers.premium_routes import _apply_subscription_event

        event = _mk_event("evt_4", "customer.subscription.updated", customer_id="cus_unknown")
        # Should not raise.
        _apply_subscription_event(self.db, event)


if __name__ == "__main__":
    unittest.main()
