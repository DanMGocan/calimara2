"""'Cumpără-mi o cafea': one-time Stripe payment, any quantity, trophy for logged-in buyers."""

import hashlib
import hmac
import json
import os
import time
import unittest
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
os.environ["STRIPE_SUCCESS_URL"] = "http://x/premium?plata=succes"
os.environ["STRIPE_CANCEL_URL"] = "http://x/cancel"
os.environ["STRIPE_CUSTOMER_PORTAL_RETURN_URL"] = "http://x/panou"

from app import auth, models, stripe_service
from app.database import get_db
from app.routers import premium_routes

stripe_service._refresh_config_from_env_if_enabled()

COFFEE_PRICE = {"unit_amount": 1200, "currency": "ron", "recurring": None, "active": True}


def _sign(payload: str) -> str:
    ts = int(time.time())
    sig = hmac.new(b"whsec_dummy", f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


class _Url:
    url = "https://checkout.stripe.test/c"


class CoffeeServiceTests(unittest.TestCase):
    def test_offer_unavailable_without_price_id(self):
        with patch.dict(os.environ, {"STRIPE_PRICE_ID_CAFEA": ""}):
            offer = stripe_service.coffee_offer()
        self.assertFalse(offer["available"])

    def test_offer_shows_lei(self):
        with patch.dict(os.environ, {"STRIPE_PRICE_ID_CAFEA": "price_cafea"}), \
                patch.object(stripe_service.stripe.Price, "retrieve", return_value=COFFEE_PRICE):
            offer = stripe_service.coffee_offer()
        self.assertTrue(offer["available"])
        self.assertEqual(offer["price"], "12,00 lei")
        self.assertEqual(offer["unit_amount"], 1200)

    def test_checkout_is_one_time_adjustable_and_clamped(self):
        with patch.dict(os.environ, {"STRIPE_PRICE_ID_CAFEA": "price_cafea", "STRIPE_COFFEE_SUCCESS_URL": ""}), \
                patch.object(stripe_service, "SUCCESS_URL", "http://x/premium?plata=succes"), \
                patch.object(stripe_service.stripe.checkout.Session, "create", return_value=_Url()) as create:
            stripe_service.create_coffee_checkout_session(99, user_id=5, customer_id="cus_5")
        kw = create.call_args.kwargs
        self.assertEqual(kw["mode"], "payment")
        self.assertEqual(kw["submit_type"], "donate")
        item = kw["line_items"][0]
        self.assertEqual(item["price"], "price_cafea")
        self.assertEqual(item["quantity"], stripe_service.COFFEE_MAX_QUANTITY)
        self.assertTrue(item["adjustable_quantity"]["enabled"])
        self.assertEqual(kw["metadata"], {"kind": "coffee", "user_id": "5"})
        self.assertEqual(kw["client_reference_id"], "5")
        self.assertEqual(kw["customer"], "cus_5")
        self.assertEqual(kw["success_url"], "http://x/premium?cafea=multumim")

    def test_anonymous_checkout_has_no_user(self):
        with patch.dict(os.environ, {"STRIPE_PRICE_ID_CAFEA": "price_cafea"}), \
                patch.object(stripe_service.stripe.checkout.Session, "create", return_value=_Url()) as create:
            stripe_service.create_coffee_checkout_session(2)
        kw = create.call_args.kwargs
        self.assertNotIn("client_reference_id", kw)
        self.assertNotIn("customer", kw)
        self.assertEqual(kw["metadata"], {"kind": "coffee"})

    def test_portal_uses_pinned_configuration_when_set(self):
        with patch.dict(os.environ, {"STRIPE_PORTAL_CONFIGURATION_ID": "bpc_123"}), \
                patch.object(stripe_service.stripe.billing_portal.Session, "create", return_value=_Url()) as create:
            stripe_service.create_billing_portal_session("cus_1")
        self.assertEqual(create.call_args.kwargs["configuration"], "bpc_123")


class CoffeeEndpointTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        models.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.user = models.User(username="ana", email="ana@x.t", google_id="g-ana", stripe_customer_id="cus_ana")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)
        self.current_user = None

        app = FastAPI()
        app.include_router(premium_routes.router)

        def _db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[auth.get_current_user] = lambda: self.current_user
        self.client = TestClient(app)
        self.env = patch.dict(os.environ, {"STRIPE_PRICE_ID_CAFEA": "price_cafea"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _webhook(self, session, event_id="evt_coffee"):
        payload = json.dumps({"id": event_id, "type": "checkout.session.completed", "data": {"object": session}})
        with patch.object(stripe_service.stripe.Price, "retrieve", return_value=COFFEE_PRICE):
            return self.client.post("/api/stripe/notificare", content=payload,
                                    headers={"stripe-signature": _sign(payload), "content-type": "application/json"})

    def _session(self, **overrides):
        session = {"id": "cs_1", "mode": "payment", "payment_status": "paid", "amount_total": 3600,
                   "client_reference_id": str(self.user.id),
                   "metadata": {"kind": "coffee", "user_id": str(self.user.id)}}
        session.update(overrides)
        return session

    def _awards(self):
        return self.db.query(models.UserAward).filter_by(user_id=self.user.id, achievement_key="coffee_supporter").all()

    def test_anonymous_visitor_can_start_checkout(self):
        with patch.object(stripe_service.stripe.checkout.Session, "create", return_value=_Url()):
            resp = self.client.post("/api/premium/cafea", json={"quantity": 2})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["url"], _Url.url)

    def test_quantity_out_of_range_is_rejected(self):
        self.assertEqual(self.client.post("/api/premium/cafea", json={"quantity": 0}).status_code, 422)
        self.assertEqual(self.client.post("/api/premium/cafea", json={"quantity": 21}).status_code, 422)

    def test_paid_coffee_grants_one_trophy(self):
        self.assertEqual(self._webhook(self._session(), "evt_a").status_code, 200)
        self.assertEqual(self._webhook(self._session(id="cs_2"), "evt_b").status_code, 200)
        awards = self._awards()
        self.assertEqual(len(awards), 1)
        self.assertEqual(awards[0].award_type, "special")
        self.assertEqual(awards[0].extra_data.get("quantity"), 3)

    def test_unpaid_or_anonymous_or_subscription_sessions_grant_nothing(self):
        self._webhook(self._session(payment_status="unpaid"), "evt_u")
        self._webhook(self._session(client_reference_id=None, metadata={"kind": "coffee"}), "evt_anon")
        self._webhook(self._session(mode="subscription", metadata={"tier": "trubadur"}), "evt_sub")
        self.assertEqual(self._awards(), [])


if __name__ == "__main__":
    unittest.main()
