"""Create (or reuse) Calimara's Stripe catalog, Customer Portal and webhook.

Idempotent: prices are found by lookup_key, the portal configuration by its
metadata tag and the webhook endpoint by URL, so re-running changes nothing.
Run it once per Stripe mode (test, then live) and copy the printed lines
into .env. It does not touch the database.

    STRIPE_API_KEY=sk_test_... python scripts/stripe_bootstrap.py
    STRIPE_API_KEY=sk_live_... python scripts/stripe_bootstrap.py --webhook-url https://calimara.ro/api/stripe/notificare
"""

import argparse
import os
import sys

import stripe

CURRENCY = "ron"
# Electronically supplied services; lets Stripe Tax monitoring/collection work.
TAX_CODE = "txcd_10000000"
TIERS = [
    # (tier key, product name, monthly amount in bani, env var)
    ("trubadur", "Trubadur", 1500, "STRIPE_PRICE_ID_TRUBADUR_MONTHLY"),
    ("cronicar", "Cronicar", 3000, "STRIPE_PRICE_ID_CRONICAR_MONTHLY"),
    ("rapsod", "Rapsod", 6000, "STRIPE_PRICE_ID_RAPSOD_MONTHLY"),
]
WEBHOOK_EVENTS = [
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_failed",
]
PORTAL_TAG = "calimara_supporter_portal"


def lookup_key(tier: str) -> str:
    return f"calimara_{tier}_monthly_{CURRENCY}"


def ensure_price(tier: str, name: str, amount: int) -> stripe.Price:
    key = lookup_key(tier)
    existing = stripe.Price.list(lookup_keys=[key], active=True, limit=1).data
    if existing:
        price = existing[0]
        if price.unit_amount != amount or price.currency != CURRENCY:
            sys.exit(
                f"Price {price.id} ({key}) is {price.unit_amount} {price.currency}, expected "
                f"{amount} {CURRENCY}. Prices are immutable: archive it in the Dashboard and re-run."
            )
        print(f"# reuse  {name}: {price.id}", file=sys.stderr)
        return price
    product = stripe.Product.create(
        name=f"Calimara {name}",
        description=f"Abonament lunar de susținător Calimara – {name}",
        tax_code=TAX_CODE,
        metadata={"tier": tier},
    )
    price = stripe.Price.create(
        product=product.id,
        currency=CURRENCY,
        unit_amount=amount,
        recurring={"interval": "month"},
        lookup_key=key,
        tax_behavior="inclusive",
        metadata={"tier": tier},
    )
    print(f"# create {name}: {product.id} / {price.id}", file=sys.stderr)
    return price


def ensure_portal(prices: list) -> stripe.billing_portal.Configuration:
    features = {
        "customer_update": {"enabled": True, "allowed_updates": ["email", "address", "tax_id"]},
        "invoice_history": {"enabled": True},
        "payment_method_update": {"enabled": True},
        "subscription_cancel": {
            "enabled": True,
            "mode": "at_period_end",
            "cancellation_reason": {
                "enabled": True,
                "options": ["too_expensive", "unused", "missing_features", "other"],
            },
        },
        "subscription_update": {
            "enabled": True,
            "default_allowed_updates": ["price"],
            "proration_behavior": "create_prorations",
            "products": [{"product": p.product, "prices": [p.id]} for p in prices],
            # Upgrades apply now (prorated); downgrades wait for the period end.
            "schedule_at_period_end": {"conditions": [{"type": "decreasing_item_amount"}]},
        },
    }
    for config in stripe.billing_portal.Configuration.list(limit=100).data:
        metadata = config.metadata.to_dict() if config.metadata else {}
        if metadata.get("tag") == PORTAL_TAG:
            config = stripe.billing_portal.Configuration.modify(config.id, features=features)
            print(f"# update portal config {config.id}", file=sys.stderr)
            return config
    config = stripe.billing_portal.Configuration.create(
        features=features,
        metadata={"tag": PORTAL_TAG},
    )
    print(f"# create portal config {config.id} (default: {config.is_default}; if False, make it"
          " the default in Dashboard > Settings > Billing > Customer portal)", file=sys.stderr)
    return config


def ensure_webhook(url: str):
    for endpoint in stripe.WebhookEndpoint.list(limit=100).data:
        if endpoint.url == url:
            print(f"# reuse  webhook {endpoint.id} (signing secret is only shown at creation;"
                  " reveal it in Dashboard > Developers > Webhooks)", file=sys.stderr)
            return None
    endpoint = stripe.WebhookEndpoint.create(
        url=url,
        enabled_events=WEBHOOK_EVENTS,
        description="Calimara supporter subscriptions",
    )
    print(f"# create webhook {endpoint.id} -> {url}", file=sys.stderr)
    return endpoint.secret


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--webhook-url", help="Create a webhook endpoint for this URL (skip for local `stripe listen`).")
    args = parser.parse_args()

    stripe.api_key = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY")
    if not stripe.api_key:
        sys.exit("Set STRIPE_API_KEY (or STRIPE_SECRET_KEY).")
    print(f"# mode: {'LIVE' if stripe.api_key.startswith(('sk_live', 'rk_live')) else 'test'}", file=sys.stderr)

    prices = [ensure_price(tier, name, amount) for tier, name, amount, _ in TIERS]
    ensure_portal(prices)
    secret = ensure_webhook(args.webhook_url) if args.webhook_url else None

    print("# --- copy into .env ---")
    for (_, _, _, env_name), price in zip(TIERS, prices):
        print(f"{env_name}={price.id}")
    if secret:
        print(f"STRIPE_WEBHOOK_SECRET={secret}")


if __name__ == "__main__":
    main()
