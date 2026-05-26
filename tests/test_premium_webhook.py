import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ["STRIPE_ENABLED"] = "True"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_dummy"
os.environ["STRIPE_PRICE_ID_TRUBADUR_MONTHLY"] = "price_dummy"
os.environ["STRIPE_PRICE_ID_CRONICAR_MONTHLY"] = "price_cronicar_dummy"
os.environ["STRIPE_PRICE_ID_RAPSOD_MONTHLY"] = "price_rapsod_dummy"
os.environ["STRIPE_SUCCESS_URL"] = "http://x/success"
os.environ["STRIPE_CANCEL_URL"] = "http://x/cancel"
os.environ["STRIPE_CUSTOMER_PORTAL_RETURN_URL"] = "http://x/panou"

from app import crud, models, stripe_service
from app.week_util import utcnow_naive

stripe_service._refresh_config_from_env_if_enabled()


def _mk_event(event_id, event_type, customer_id="cus_1", sub_id="sub_1", period_end_ts=None, period_start_ts=None, tier="trubadur"):
    price_id = {
        "trubadur": "price_dummy",
        "cronicar": "price_cronicar_dummy",
        "rapsod": "price_rapsod_dummy",
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


def _mk_price(unit_amount, interval="month", active=True):
    return {
        "unit_amount": unit_amount,
        "currency": "eur",
        "recurring": {"interval": interval},
        "active": active,
    }


class PremiumPlanTests(unittest.TestCase):
    def test_plan_prices_come_from_stripe_for_every_tier(self):
        prices = {
            "price_dummy": _mk_price(399),
            "price_cronicar_dummy": _mk_price(799),
            "price_rapsod_dummy": _mk_price(1299),
        }

        with patch.object(stripe_service.stripe.Price, "retrieve", side_effect=lambda price_id: prices[price_id]):
            plans = stripe_service.list_premium_plans()

        plan_by_key = {plan["key"]: plan for plan in plans}
        self.assertEqual([plan["key"] for plan in plans], ["free", "trubadur", "cronicar", "rapsod"])
        self.assertEqual(plan_by_key["free"]["price"], "0 €")
        self.assertEqual(plan_by_key["trubadur"]["price"], "3,99 €")
        self.assertEqual(plan_by_key["cronicar"]["price"], "7,99 €")
        self.assertEqual(plan_by_key["rapsod"]["price"], "12,99 €")
        self.assertTrue(all(plan["available"] for plan in plans))
        self.assertTrue(all(plan["cadence"] == "/ lună" for plan in plans))

    def test_missing_stripe_price_id_marks_plan_unavailable(self):
        with (
            patch.object(stripe_service, "PRICE_ID_CRONICAR", ""),
            patch.object(stripe_service.stripe.Price, "retrieve", return_value=_mk_price(399)),
        ):
            plans = stripe_service.list_premium_plans()

        plan_by_key = {plan["key"]: plan for plan in plans}
        self.assertFalse(plan_by_key["cronicar"]["available"])
        self.assertEqual(plan_by_key["cronicar"]["price"], "Indisponibil")


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
        self.assertEqual(self.user.premium_tier, "trubadur")

    def test_process_audio_subscription_sets_audio_tier(self):
        from app.routers.premium_routes import _apply_subscription_event

        event = _mk_event("evt_audio", "customer.subscription.updated", tier="cronicar")
        _apply_subscription_event(self.db, event)
        self.db.refresh(self.user)
        self.assertEqual(self.user.premium_tier, "cronicar")
        self.assertTrue(self.user.has_audio_access)
        self.assertFalse(self.user.has_author_audio_access)

    def test_process_author_audio_subscription_sets_author_audio_tier(self):
        from app.routers.premium_routes import _apply_subscription_event

        event = _mk_event("evt_author_audio", "customer.subscription.updated", tier="rapsod")
        _apply_subscription_event(self.db, event)
        self.db.refresh(self.user)
        self.assertEqual(self.user.premium_tier, "rapsod")
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
