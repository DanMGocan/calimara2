import os
from typing import Optional

import stripe


STRIPE_ENABLED = os.getenv("STRIPE_ENABLED", "False").lower() in ("true", "1", "yes")


def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(
            f"{name} is required when STRIPE_ENABLED=True. Set it in .env."
        )
    return val


if STRIPE_ENABLED:
    stripe.api_key = _require("STRIPE_SECRET_KEY")
    WEBHOOK_SECRET = _require("STRIPE_WEBHOOK_SECRET")
    PRICE_ID_PREMIUM = _require("STRIPE_PRICE_ID_PREMIUM_MONTHLY")
    PRICE_ID_AUDIO = os.getenv("STRIPE_PRICE_ID_AUDIO_MONTHLY", "")
    PRICE_ID_AUTHOR_AUDIO = os.getenv("STRIPE_PRICE_ID_AUTHOR_AUDIO_MONTHLY", "")
    SUCCESS_URL = _require("STRIPE_SUCCESS_URL")
    CANCEL_URL = _require("STRIPE_CANCEL_URL")
    PORTAL_RETURN_URL = _require("STRIPE_CUSTOMER_PORTAL_RETURN_URL")
else:
    WEBHOOK_SECRET = PRICE_ID_PREMIUM = PRICE_ID_AUDIO = PRICE_ID_AUTHOR_AUDIO = SUCCESS_URL = CANCEL_URL = PORTAL_RETURN_URL = ""


def ensure_enabled() -> None:
    if not STRIPE_ENABLED:
        raise RuntimeError("Stripe is disabled. Set STRIPE_ENABLED=True in .env.")


def create_or_get_customer(email: str, user_id: int, existing_customer_id: Optional[str]) -> str:
    ensure_enabled()
    if existing_customer_id:
        return existing_customer_id
    customer = stripe.Customer.create(
        email=email,
        metadata={"user_id": str(user_id)},
    )
    return customer.id


def price_id_for_tier(tier: str) -> str:
    if tier == "author_audio":
        if not PRICE_ID_AUTHOR_AUDIO:
            raise RuntimeError("STRIPE_PRICE_ID_AUTHOR_AUDIO_MONTHLY is required for La cenaclu' Flacara checkout.")
        return PRICE_ID_AUTHOR_AUDIO
    if tier == "audio":
        if not PRICE_ID_AUDIO:
            raise RuntimeError("STRIPE_PRICE_ID_AUDIO_MONTHLY is required for Membru Junimea checkout.")
        return PRICE_ID_AUDIO
    return PRICE_ID_PREMIUM


def subscription_tier_from_event_object(data) -> str:
    metadata_tier = (data.get("metadata") or {}).get("tier")
    if metadata_tier in {"premium", "audio", "author_audio"}:
        return metadata_tier
    items = ((data.get("items") or {}).get("data") or [])
    for item in items:
        price_id = (((item or {}).get("price") or {}).get("id"))
        if price_id and PRICE_ID_AUTHOR_AUDIO and price_id == PRICE_ID_AUTHOR_AUDIO:
            return "author_audio"
        if price_id and PRICE_ID_AUDIO and price_id == PRICE_ID_AUDIO:
            return "audio"
        if price_id and price_id == PRICE_ID_PREMIUM:
            return "premium"
    return "premium"


def create_checkout_session(customer_id: str, user_id: int, tier: str = "premium") -> str:
    ensure_enabled()
    price_id = price_id_for_tier(tier)
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        client_reference_id=str(user_id),
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=SUCCESS_URL,
        cancel_url=CANCEL_URL,
        metadata={"user_id": str(user_id), "tier": tier},
        subscription_data={"metadata": {"user_id": str(user_id), "tier": tier}},
    )
    return session.url


def create_billing_portal_session(customer_id: str) -> str:
    ensure_enabled()
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=PORTAL_RETURN_URL,
    )
    return session.url


def verify_webhook(payload: bytes, sig_header: str):
    ensure_enabled()
    return stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
