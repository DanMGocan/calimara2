"""Webhook hardening: real stripe-python objects, API >= 2025-03-31 payloads,
subscription status gating, retry-safe idempotency, and RON pricing."""

import hashlib
import hmac
import json
import os
import time
import unittest
from datetime import timedelta
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
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
from app.database import get_db
from app.routers import premium_routes
from app.week_util import utcnow_naive

stripe_service._refresh_config_from_env_if_enabled()


def _ts(delta: timedelta) -> int:
    return int((utcnow_naive() + delta).timestamp())


def _subscription_event(event_id="evt_1", status="active", event_type="customer.subscription.updated",
                        tier="cronicar", top_level_period=False):
    item = {
        "id": "si_1",
        "object": "subscription_item",
        "price": {"id": "price_cronicar_dummy", "object": "price"},
        "current_period_start": _ts(timedelta(hours=-1)),
        "current_period_end": _ts(timedelta(days=30)),
    }
    sub = {
        "id": "sub_1",
        "object": "subscription",
        "customer": "cus_1",
        "status": status,
        "metadata": {"tier": tier},
        "items": {"object": "list", "data": [item]},
    }
    if top_level_period:
        sub["current_period_start"] = item["current_period_start"]
        sub["current_period_end"] = item["current_period_end"]
    return {"id": event_id, "object": "event", "type": event_type, "data": {"object": sub}}


def _sign(payload: str, secret: str = "whsec_dummy") -> str:
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


class _DbCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        models.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.user = models.User(
            username="alice", email="a@x.t", google_id="g-a", stripe_customer_id="cus_1"
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()


class VerifyWebhookTests(unittest.TestCase):
    def test_returns_plain_dicts_for_a_validly_signed_payload(self):
        payload = json.dumps(_subscription_event())
        event = stripe_service.verify_webhook(payload.encode(), _sign(payload))
        data = event["data"]["object"]
        self.assertIsInstance(data, dict)
        # Handlers rely on dict.get(); real StripeObjects (stripe-python >= 15) lack it.
        self.assertEqual(data.get("customer"), "cus_1")

    def test_rejects_a_bad_signature(self):
        payload = json.dumps(_subscription_event())
        with self.assertRaises(Exception):
            stripe_service.verify_webhook(payload.encode(), _sign(payload, secret="whsec_other"))


class SubscriptionEventTests(_DbCase):
    def test_period_fields_only_on_items_still_grant_premium(self):
        premium_routes._apply_subscription_event(self.db, _subscription_event())
        self.db.refresh(self.user)
        self.assertEqual(self.user.premium_tier, "cronicar")
        self.assertEqual(self.user.stripe_subscription_id, "sub_1")
        self.assertIsNotNone(self.user.premium_until)
        self.assertIsNotNone(self.user.premium_period_start)

    def test_portal_plan_switch_uses_new_price_over_stale_metadata(self):
        # Checkout wrote metadata tier=trubadur; the customer later upgraded
        # to Rapsod in the Customer Portal, which only changes the price.
        event = _subscription_event(tier="trubadur")
        event["data"]["object"]["items"]["data"][0]["price"]["id"] = "price_rapsod_dummy"
        premium_routes._apply_subscription_event(self.db, event)
        self.db.refresh(self.user)
        self.assertEqual(self.user.premium_tier, "rapsod")

    def test_incomplete_subscription_does_not_grant_premium(self):
        premium_routes._apply_subscription_event(self.db, _subscription_event(status="incomplete"))
        self.db.refresh(self.user)
        self.assertEqual(self.user.premium_tier, "free")
        self.assertIsNone(self.user.premium_until)

    def test_past_due_subscription_does_not_extend_premium(self):
        paid_until = utcnow_naive() + timedelta(days=2)
        crud.set_premium_from_subscription(
            self.db, user_id=self.user.id, subscription_id="sub_1",
            premium_until=paid_until, premium_tier="cronicar",
        )
        premium_routes._apply_subscription_event(self.db, _subscription_event(status="past_due"))
        self.db.refresh(self.user)
        self.assertEqual(self.user.premium_until.replace(microsecond=0), paid_until.replace(microsecond=0))


class WebhookEndpointTests(_DbCase):
    def setUp(self):
        super().setUp()
        app = FastAPI()
        app.include_router(premium_routes.router)

        def _db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _db
        self.client = TestClient(app)

    def _post(self, event):
        payload = json.dumps(event)
        return self.client.post(
            "/api/stripe/notificare",
            content=payload,
            headers={"stripe-signature": _sign(payload), "content-type": "application/json"},
        )

    def test_signed_event_is_applied_and_recorded(self):
        resp = self._post(_subscription_event(event_id="evt_ok"))
        self.assertEqual(resp.status_code, 200)
        self.db.refresh(self.user)
        self.assertEqual(self.user.premium_tier, "cronicar")
        self.assertTrue(crud.stripe_event_already_processed(self.db, "evt_ok"))

    def test_failed_handling_returns_500_and_is_not_recorded(self):
        with patch.object(premium_routes, "_apply_subscription_event", side_effect=RuntimeError("boom")):
            resp = self._post(_subscription_event(event_id="evt_fail"))
        self.assertEqual(resp.status_code, 500)
        self.assertFalse(crud.stripe_event_already_processed(self.db, "evt_fail"))
        # Stripe's retry then succeeds.
        self.assertEqual(self._post(_subscription_event(event_id="evt_fail")).status_code, 200)
        self.assertTrue(crud.stripe_event_already_processed(self.db, "evt_fail"))

    def test_duplicate_delivery_is_a_no_op(self):
        self.assertEqual(self._post(_subscription_event(event_id="evt_dup")).status_code, 200)
        with patch.object(premium_routes, "_apply_subscription_event") as handler:
            self.assertEqual(self._post(_subscription_event(event_id="evt_dup")).status_code, 200)
        handler.assert_not_called()


class RonPricingTests(unittest.TestCase):
    def test_ron_prices_display_in_lei(self):
        prices = {
            "price_dummy": {"unit_amount": 1500, "currency": "ron", "recurring": {"interval": "month"}, "active": True},
            "price_cronicar_dummy": {"unit_amount": 3000, "currency": "ron", "recurring": {"interval": "month"}, "active": True},
            "price_rapsod_dummy": {"unit_amount": 6000, "currency": "ron", "recurring": {"interval": "month"}, "active": True},
        }
        with patch.object(stripe_service.stripe.Price, "retrieve", side_effect=lambda pid: prices[pid]):
            plans = {p["key"]: p for p in stripe_service.list_premium_plans()}
        self.assertEqual(plans["free"]["price"], "0 lei")
        self.assertEqual(plans["trubadur"]["price"], "15,00 lei")
        self.assertEqual(plans["cronicar"]["price"], "30,00 lei")
        self.assertEqual(plans["rapsod"]["price"], "60,00 lei")

    def test_checkout_uses_flexible_billing_mode(self):
        class _Session:
            url = "https://checkout.stripe.test/s"

        with patch.object(stripe_service.stripe.checkout.Session, "create", return_value=_Session()) as create:
            url = stripe_service.create_checkout_session("cus_1", 7, tier="rapsod")
        self.assertEqual(url, _Session.url)
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["mode"], "subscription")
        self.assertEqual(kwargs["line_items"], [{"price": "price_rapsod_dummy", "quantity": 1}])
        self.assertEqual(kwargs["subscription_data"]["billing_mode"], {"type": "flexible"})
        self.assertEqual(kwargs["subscription_data"]["metadata"]["tier"], "rapsod")


if __name__ == "__main__":
    unittest.main()
