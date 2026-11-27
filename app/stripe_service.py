import json
import os
from decimal import Decimal, InvalidOperation
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

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


PREMIUM_PAID_TIER_ORDER = ("trubadur", "cronicar", "rapsod")
PREMIUM_TIER_ORDER = ("free", *PREMIUM_PAID_TIER_ORDER)

PREMIUM_TIER_DETAILS = {
    "free": {
        "name": "Gratuit",
        "eyebrow": "Start",
        "summary": "Pentru cititori și autori care vor să publice, să citească și să folosească instrumentele de bază.",
        "benefits": [
            "1 super-apreciere pe lună",
            "15.000 caractere pentru Diacritice pe lună",
            "1.000 caractere pentru generare audio pe lună",
            "20 de minute pe zi în playerul audio",
            "Publicare poezie și proză scurtă cu moderare",
            "Comentarii, aprecieri, urmăriri și prieteni",
            "Recomandări cu recompense Trubadur",
        ],
    },
    "trubadur": {
        "name": "Trubadur",
        "eyebrow": "Bronz",
        "summary": "Super-aprecieri, ascultare nelimitată în playerul audio și funcțiile premium de bază.",
        "benefits": [
            "3 super-aprecieri pe lună",
            "Player audio nelimitat",
            "60.000 caractere pentru Diacritice pe lună",
            "50.000 caractere pentru generare audio pe lună",
            "Experiență fără reclame când ești conectat",
            "Imagine de profil și copertă premium",
        ],
    },
    "cronicar": {
        "name": "Cronicar",
        "eyebrow": "Argint",
        "summary": "Generează audio pentru textele tale: 100.000 caractere per ciclu de facturare.",
        "benefits": [
            "Tot ce include Trubadur",
            "4 super-aprecieri pe lună",
            "120.000 caractere pentru Diacritice pe lună",
            "100.000 caractere pentru generare audio",
            "Conversie text în fișier audio pentru textele tale",
            "Administrare audio din dashboard",
            "Analitice avansate zilnice prin email",
        ],
    },
    "rapsod": {
        "name": "Rapsod",
        "eyebrow": "Aur",
        "summary": "Generează 200.000 caractere per ciclu și poți încărca înregistrări audio de autor.",
        "benefits": [
            "Tot ce include Cronicar",
            "5 super-aprecieri pe lună",
            "180.000 caractere pentru Diacritice pe lună",
            "200.000 caractere pentru generare audio",
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
    "ron": "lei",
}
FREE_TIER_PRICE_LABEL = "0 lei"


def ensure_enabled() -> None:
    _refresh_config_from_env_if_enabled()
    if not STRIPE_ENABLED:
        raise RuntimeError("Stripe is disabled. Set STRIPE_ENABLED=True in .env.")


def _refresh_config_from_env_if_enabled() -> None:
    global STRIPE_ENABLED, WEBHOOK_SECRET, PRICE_ID_TRUBADUR, PRICE_ID_CRONICAR, PRICE_ID_RAPSOD, SUCCESS_URL, CANCEL_URL, PORTAL_RETURN_URL
    if STRIPE_ENABLED:
        return
    if os.getenv("STRIPE_ENABLED", "False").lower() not in ("true", "1", "yes"):
        return
    STRIPE_ENABLED = True
    stripe.api_key = _require("STRIPE_SECRET_KEY")
    WEBHOOK_SECRET = _require("STRIPE_WEBHOOK_SECRET")
    PRICE_ID_TRUBADUR = _require("STRIPE_PRICE_ID_TRUBADUR_MONTHLY")
    PRICE_ID_CRONICAR = os.getenv("STRIPE_PRICE_ID_CRONICAR_MONTHLY", "")
    PRICE_ID_RAPSOD = os.getenv("STRIPE_PRICE_ID_RAPSOD_MONTHLY", "")
    SUCCESS_URL = _require("STRIPE_SUCCESS_URL")
    CANCEL_URL = _require("STRIPE_CANCEL_URL")
    PORTAL_RETURN_URL = _require("STRIPE_CUSTOMER_PORTAL_RETURN_URL")


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
    _refresh_config_from_env_if_enabled()
    if tier == "free":
        return ""
    if tier == "rapsod":
        return PRICE_ID_RAPSOD
    if tier == "cronicar":
        return PRICE_ID_CRONICAR
    return PRICE_ID_TRUBADUR


def price_id_for_tier(tier: str) -> str:
    if tier not in PREMIUM_PAID_TIER_ORDER:
        raise RuntimeError("Tier premium invalid pentru checkout.")
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
    currency = str(_object_value(price, "currency", "ron") or "ron")
    return _format_major_amount(amount, currency)


def _stripe_price_cadence(price) -> str:
    recurring = _object_value(price, "recurring") or {}
    interval = _object_value(recurring, "interval")
    return CADENCE_BY_STRIPE_INTERVAL.get(interval, "")


def _stripe_price_payload_for_tier(tier: str) -> dict:
    if tier == "free":
        return {"price": FREE_TIER_PRICE_LABEL, "cadence": "/ lună", "available": True}
    _refresh_config_from_env_if_enabled()
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
    """Tier for a subscription, from its current price.

    The price wins over ``metadata.tier``: the metadata is written once at
    Checkout, but customers can switch plans in the Customer Portal, which
    changes the price and leaves the metadata stale.
    """
    _refresh_config_from_env_if_enabled()
    items = ((data.get("items") or {}).get("data") or [])
    for item in items:
        price_id = (((item or {}).get("price") or {}).get("id"))
        if price_id and PRICE_ID_RAPSOD and price_id == PRICE_ID_RAPSOD:
            return "rapsod"
        if price_id and PRICE_ID_CRONICAR and price_id == PRICE_ID_CRONICAR:
            return "cronicar"
        if price_id and PRICE_ID_TRUBADUR and price_id == PRICE_ID_TRUBADUR:
            return "trubadur"
    metadata_tier = (data.get("metadata") or {}).get("tier")
    if metadata_tier in {"trubadur", "cronicar", "rapsod"}:
        return metadata_tier
    return "trubadur"


def _terms_url() -> str:
    scheme = (os.getenv("PUBLIC_SCHEME") or "https").strip() or "https"
    domain = (os.getenv("MAIN_DOMAIN") or "calimara.ro").strip() or "calimara.ro"
    return f"{scheme}://{domain}/termeni"


def terms_consent_params(kind: str) -> dict:
    """Checkout must show a required "I accept the terms" checkbox.

    Off unless STRIPE_REQUIRE_TERMS is true: Stripe rejects the session until a
    terms of service URL is saved in Dashboard > Settings > Public details.
    """
    if os.getenv("STRIPE_REQUIRE_TERMS", "false").strip().lower() not in ("true", "1", "yes"):
        return {}
    if kind == "subscription":
        message = (
            f"Accept [Termenii și condițiile]({_terms_url()}) și cer ca Premium să înceapă imediat. "
            "Abonamentul se reînnoiește lunar până îl anulezi. Poți cere rambursarea integrală "
            "a primei plăți în 14 zile."
        )
    else:
        message = (
            f"Accept [Termenii și condițiile]({_terms_url()}). "
            "Poți cere rambursarea integrală în 14 zile de la plată."
        )
    return {
        "consent_collection": {"terms_of_service": "required"},
        "custom_text": {"terms_of_service_acceptance": {"message": message}},
    }


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
        subscription_data={
            "metadata": {"user_id": str(user_id), "tier": tier},
            # Flexible billing mode: Stripe's recommended default for new
            # subscriptions (accurate proration on upgrades/downgrades).
            "billing_mode": {"type": "flexible"},
        },
        **terms_consent_params("subscription"),
    )
    return session.url


def create_billing_portal_session(customer_id: str) -> str:
    ensure_enabled()
    params = {"customer": customer_id, "return_url": PORTAL_RETURN_URL}
    # Optional: pin the portal configuration created by scripts/stripe_bootstrap.py
    # (plan switching between tiers). Without it Stripe uses the account default.
    configuration = os.getenv("STRIPE_PORTAL_CONFIGURATION_ID", "").strip()
    if configuration:
        params["configuration"] = configuration
    session = stripe.billing_portal.Session.create(**params)
    return session.url


# ---------- "Cumpără-mi o cafea": one-time support, any quantity ----------

COFFEE_KIND = "coffee"
COFFEE_MAX_QUANTITY = 20


def coffee_price_id() -> str:
    return os.getenv("STRIPE_PRICE_ID_CAFEA", "").strip()


def _coffee_success_url() -> str:
    explicit = os.getenv("STRIPE_COFFEE_SUCCESS_URL", "").strip()
    if explicit:
        return explicit
    parts = urlsplit(SUCCESS_URL)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "cafea=multumim", ""))


def coffee_offer() -> dict:
    """Price of one coffee, for the premium page; unavailable if not configured."""
    unavailable = {"available": False, "price": PRICE_UNAVAILABLE_LABEL, "unit_amount": None,
                   "currency": None, "max_quantity": COFFEE_MAX_QUANTITY}
    _refresh_config_from_env_if_enabled()
    price_id = coffee_price_id()
    if not STRIPE_ENABLED or not price_id:
        return unavailable
    try:
        price = stripe.Price.retrieve(price_id)
    except Exception:
        return unavailable
    unit_amount = _object_value(price, "unit_amount")
    price_text = _stripe_price_display(price)
    if not _object_value(price, "active", True) or unit_amount is None or price_text == PRICE_UNAVAILABLE_LABEL:
        return unavailable
    return {
        "available": True,
        "price": price_text,
        "unit_amount": int(unit_amount),
        "currency": str(_object_value(price, "currency", "ron")),
        "max_quantity": COFFEE_MAX_QUANTITY,
    }


def create_coffee_checkout_session(
    quantity: int,
    user_id: Optional[int] = None,
    customer_id: Optional[str] = None,
) -> str:
    ensure_enabled()
    price_id = coffee_price_id()
    if not price_id:
        raise RuntimeError("STRIPE_PRICE_ID_CAFEA is required for coffee checkout.")
    quantity = max(1, min(int(quantity), COFFEE_MAX_QUANTITY))
    metadata = {"kind": COFFEE_KIND}
    if user_id is not None:
        metadata["user_id"] = str(user_id)
    params = {
        "mode": "payment",
        "submit_type": "donate",
        "locale": "ro",
        "line_items": [{
            "price": price_id,
            "quantity": quantity,
            "adjustable_quantity": {"enabled": True, "minimum": 1, "maximum": COFFEE_MAX_QUANTITY},
        }],
        "success_url": _coffee_success_url(),
        "cancel_url": CANCEL_URL,
        "metadata": metadata,
        "payment_intent_data": {"metadata": metadata, "description": "Cumpără-mi o cafea – Călimara"},
    }
    if user_id is not None:
        params["client_reference_id"] = str(user_id)
    if customer_id:
        params["customer"] = customer_id
    params.update(terms_consent_params("coffee"))
    session = stripe.checkout.Session.create(**params)
    return session.url


def is_paid_coffee_session(session: dict) -> bool:
    return (
        (session.get("metadata") or {}).get("kind") == COFFEE_KIND
        and session.get("mode") == "payment"
        and session.get("payment_status") == "paid"
    )


def coffee_quantity_from_session(session: dict) -> Optional[int]:
    """Quantity bought; Stripe only includes line items when expanded, so this
    may be None. Derive it from the amount when the unit price is known."""
    amount_total = session.get("amount_total")
    price_id = coffee_price_id()
    if amount_total is None or not price_id:
        return None
    try:
        unit = _object_value(stripe.Price.retrieve(price_id), "unit_amount")
    except Exception:
        return None
    if not unit:
        return None
    return max(1, round(int(amount_total) / int(unit)))


def verify_webhook(payload: bytes, sig_header: str) -> dict:
    """Verify the Stripe signature and return the event as plain dicts.

    stripe-python >= 15 returns StripeObjects that no longer support
    ``.get()``; the webhook handlers work on dicts, so after the signature
    check we parse the raw payload ourselves.
    """
    ensure_enabled()
    stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    return json.loads(payload)
