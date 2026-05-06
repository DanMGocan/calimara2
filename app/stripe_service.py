import os
from decimal import Decimal, InvalidOperation
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
    PRICE_ID_TRUBADUR = _require("STRIPE_PRICE_ID_TRUBADUR_MONTHLY")
    PRICE_ID_CRONICAR = os.getenv("STRIPE_PRICE_ID_CRONICAR_MONTHLY", "")
    PRICE_ID_RAPSOD = os.getenv("STRIPE_PRICE_ID_RAPSOD_MONTHLY", "")
    SUCCESS_URL = _require("STRIPE_SUCCESS_URL")
    CANCEL_URL = _require("STRIPE_CANCEL_URL")
    PORTAL_RETURN_URL = _require("STRIPE_CUSTOMER_PORTAL_RETURN_URL")
else:
    WEBHOOK_SECRET = PRICE_ID_TRUBADUR = PRICE_ID_CRONICAR = PRICE_ID_RAPSOD = SUCCESS_URL = CANCEL_URL = PORTAL_RETURN_URL = ""


PREMIUM_TIER_ORDER = ("trubadur", "cronicar", "rapsod")

PREMIUM_TIER_DETAILS = {
    "trubadur": {
        "name": "Trubadur",
        "eyebrow": "Premium",
        "summary": "Super-aprecieri și funcțiile premium de bază. Ascultarea audio este publică.",
        "benefits": [
            "3 super-aprecieri pe săptămână",
            "Conversie automată la diacritice",
            "Experiență fără reclame când ești conectat",
            "Imagine de profil și copertă premium",
        ],
    },
    "cronicar": {
        "name": "Cronicar",
        "eyebrow": "Audio",
        "summary": "Generează audio pentru textele tale: 100.000 caractere per ciclu de facturare.",
        "benefits": [
            "Tot ce include Trubadur",
            "100.000 caractere pentru generare audio",
            "Conversie text în fișier audio pentru textele tale",
            "Administrare audio din dashboard",
        ],
    },
    "rapsod": {
        "name": "Rapsod",
        "eyebrow": "Audio de autor",
        "summary": "Generează 250.000 caractere per ciclu și poți încărca înregistrări audio de autor.",
        "benefits": [
            "Tot ce include Cronicar",
            "250.000 caractere pentru generare audio",
            "Încărcare înregistrări audio de autor",
            "Moderare și publicare audio pentru postări aprobate",
        ],
    },
}

PRICE_UNAVAILABLE_LABEL = "Indisponibil"
CADENCE_BY_STRIPE_INTERVAL = {
    "day": "/ zi",
    "week": "/ săptămână",
    "month": "/ lună",
    "year": "/ an",
}
CURRENCY_SYMBOLS = {
    "eur": "€",
    "usd": "$",
    "gbp": "£",
}


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


def configured_price_id_for_tier(tier: str) -> str:
    if tier == "rapsod":
        return PRICE_ID_RAPSOD
    if tier == "cronicar":
        return PRICE_ID_CRONICAR
    return PRICE_ID_TRUBADUR


def price_id_for_tier(tier: str) -> str:
    price_id = configured_price_id_for_tier(tier)
    if price_id:
        return price_id
    tier_name = PREMIUM_TIER_DETAILS.get(tier, PREMIUM_TIER_DETAILS["trubadur"])["name"]
    env_name = f"STRIPE_PRICE_ID_{tier.upper()}_MONTHLY"
    raise RuntimeError(f"{env_name} is required for {tier_name} checkout.")


def _object_value(obj, key: str, default=None):
    if hasattr(obj, "get"):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _format_major_amount(amount: Decimal, currency: str) -> str:
    text = f"{amount.quantize(Decimal('0.01')):,.2f}"
    text = text.replace(",", "X").replace(".", ",").replace("X", ".")
    suffix = CURRENCY_SYMBOLS.get(currency.lower(), currency.upper())
    return f"{text} {suffix}"


def _stripe_price_display(price) -> str:
    unit_amount = _object_value(price, "unit_amount")
    unit_amount_decimal = _object_value(price, "unit_amount_decimal")
    try:
        if unit_amount is not None:
            amount = Decimal(int(unit_amount)) / Decimal(100)
        elif unit_amount_decimal is not None:
            amount = Decimal(str(unit_amount_decimal)) / Decimal(100)
        else:
            return PRICE_UNAVAILABLE_LABEL
    except (InvalidOperation, TypeError, ValueError):
        return PRICE_UNAVAILABLE_LABEL
    currency = str(_object_value(price, "currency", "eur") or "eur")
    return _format_major_amount(amount, currency)


def _stripe_price_cadence(price) -> str:
    recurring = _object_value(price, "recurring") or {}
    interval = _object_value(recurring, "interval")
    return CADENCE_BY_STRIPE_INTERVAL.get(interval, "")


def _stripe_price_payload_for_tier(tier: str) -> dict:
    if not STRIPE_ENABLED:
        return {"price": PRICE_UNAVAILABLE_LABEL, "cadence": "", "available": False}
    price_id = configured_price_id_for_tier(tier)
    if not price_id:
        return {"price": PRICE_UNAVAILABLE_LABEL, "cadence": "", "available": False}
    try:
        price = stripe.Price.retrieve(price_id)
    except Exception:
        return {"price": PRICE_UNAVAILABLE_LABEL, "cadence": "", "available": False}
    price_text = _stripe_price_display(price)
    is_active = bool(_object_value(price, "active", True))
    return {
        "price": price_text,
        "cadence": _stripe_price_cadence(price),
        "available": bool(is_active and price_text != PRICE_UNAVAILABLE_LABEL),
    }


def list_premium_plans() -> list[dict]:
    plans = []
    for tier in PREMIUM_TIER_ORDER:
        details = PREMIUM_TIER_DETAILS[tier]
        plans.append(
            {
                "key": tier,
                **details,
                **_stripe_price_payload_for_tier(tier),
            }
        )
    return plans


def subscription_tier_from_event_object(data) -> str:
    metadata_tier = (data.get("metadata") or {}).get("tier")
    if metadata_tier in {"trubadur", "cronicar", "rapsod"}:
        return metadata_tier
    items = ((data.get("items") or {}).get("data") or [])
    for item in items:
        price_id = (((item or {}).get("price") or {}).get("id"))
        if price_id and PRICE_ID_RAPSOD and price_id == PRICE_ID_RAPSOD:
            return "rapsod"
        if price_id and PRICE_ID_CRONICAR and price_id == PRICE_ID_CRONICAR:
            return "cronicar"
        if price_id and price_id == PRICE_ID_TRUBADUR:
            return "trubadur"
    return "trubadur"


def create_checkout_session(customer_id: str, user_id: int, tier: str = "trubadur") -> str:
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
