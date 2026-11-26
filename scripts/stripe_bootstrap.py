"""Create (or reuse) Calimara's Stripe catalog, Customer Portal and webhook.

Idempotent: prices are found by lookup_key, the portal configuration by its
metadata tag and the webhook endpoint by URL, so re-running changes nothing.
Products you already made in the Dashboard are adopted, not duplicated: an
active RON price with the right amount and interval whose product name
contains the tier name ("Trubadur", "Cronicar", "Rapsod", "cafea") gets the
lookup_key set on it. Run it once per Stripe mode (test, live) and copy the
printed lines into .env. It does not touch the database.

    STRIPE_API_KEY=sk_test_... python scripts/stripe_bootstrap.py
    STRIPE_API_KEY=sk_live_... python scripts/stripe_bootstrap.py --webhook-url https://calimara.ro/api/stripe/notificare
    (add --dry-run to only report what it would do)
"""

import argparse
import os
import sys
import unicodedata

import stripe

CURRENCY = "ron"
# Electronically supplied services; lets Stripe Tax monitoring/collection work.
TAX_CODE = "txcd_10000000"
# (key, name used to match Dashboard products, product name if created,
#  amount in bani, recurring interval or None for one-time, env var)
ITEMS = [
    ("trubadur", "trubadur", "Calimara Trubadur", 1500, "month", "STRIPE_PRICE_ID_TRUBADUR_MONTHLY"),
    ("cronicar", "cronicar", "Calimara Cronicar", 3000, "month", "STRIPE_PRICE_ID_CRONICAR_MONTHLY"),
    ("rapsod", "rapsod", "Calimara Rapsod", 6000, "month", "STRIPE_PRICE_ID_RAPSOD_MONTHLY"),
    ("cafea", "cafea", "Cumpără-mi o cafea", 1200, None, "STRIPE_PRICE_ID_CAFEA"),
]
SUBSCRIPTION_KEYS = {"trubadur", "cronicar", "rapsod"}
WEBHOOK_EVENTS = [
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_failed",
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
]
PORTAL_TAG = "calimara_supporter_portal"
DRY_RUN = False


def log(msg: str) -> None:
    print(f"# {msg}", file=sys.stderr)


def fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()


def lookup_key(key: str) -> str:
    return f"calimara_{key}_monthly_{CURRENCY}" if key in SUBSCRIPTION_KEYS else f"calimara_{key}_{CURRENCY}"


def price_interval(price):
    return price.recurring.interval if price.recurring else None


def adopt_dashboard_price(key: str, match: str, amount: int, interval):
    """Find a matching active price made by hand in the Dashboard."""
    candidates = []
    for price in stripe.Price.list(active=True, currency=CURRENCY, expand=["data.product"], limit=100).auto_paging_iter():
        product = price.product
        if not getattr(product, "active", True):
            continue
        if price.unit_amount == amount and price_interval(price) == interval and match in fold(product.name):
            candidates.append(price)
    if len(candidates) > 1:
        sys.exit(f"Several Dashboard prices match '{match}' ({[p.id for p in candidates]}). "
                 f"Archive the extras, or set lookup key {lookup_key(key)} on the right one, and re-run.")
    return candidates[0] if candidates else None


def ensure_price(key, match, product_name, amount, interval):
    lk = lookup_key(key)
    existing = stripe.Price.list(lookup_keys=[lk], active=True, limit=1).data
    if existing:
        price = existing[0]
        if price.unit_amount != amount or price.currency != CURRENCY or price_interval(price) != interval:
            sys.exit(f"Price {price.id} ({lk}) is {price.unit_amount} {price.currency} / {price_interval(price)}, "
                     f"expected {amount} {CURRENCY} / {interval}. Prices are immutable: archive it and re-run.")
        log(f"reuse  {key}: {price.id}")
        return price

    adopted = adopt_dashboard_price(key, match, amount, interval)
    if adopted:
        log(f"adopt  {key}: {adopted.id} (product '{adopted.product.name}')")
        if not DRY_RUN:
            adopted = stripe.Price.modify(adopted.id, lookup_key=lk, metadata={"tier": key})
        return adopted

    if DRY_RUN:
        log(f"would create {key}: {amount / 100:.2f} {CURRENCY} / {interval or 'one-time'}")
        return None
    product = stripe.Product.create(name=product_name, tax_code=TAX_CODE, metadata={"tier": key})
    params = dict(product=product.id, currency=CURRENCY, unit_amount=amount, lookup_key=lk,
                  tax_behavior="inclusive", metadata={"tier": key})
    if interval:
        params["recurring"] = {"interval": interval}
    price = stripe.Price.create(**params)
    log(f"create {key}: {product.id} / {price.id}")
    return price


def ensure_portal(prices: list):
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
            "products": [{"product": p.product if isinstance(p.product, str) else p.product.id, "prices": [p.id]}
                         for p in prices],
            # Upgrades apply now (prorated); downgrades wait for the period end.
            "schedule_at_period_end": {"conditions": [{"type": "decreasing_item_amount"}]},
        },
    }
    for config in stripe.billing_portal.Configuration.list(limit=100).auto_paging_iter():
        metadata = config.metadata.to_dict() if config.metadata else {}
        if metadata.get("tag") == PORTAL_TAG:
            if DRY_RUN:
                log(f"would update portal config {config.id}")
                return config
            config = stripe.billing_portal.Configuration.modify(config.id, features=features)
            log(f"update portal config {config.id}")
            return config
    if DRY_RUN:
        log("would create portal config")
        return None
    config = stripe.billing_portal.Configuration.create(features=features, metadata={"tag": PORTAL_TAG})
    log(f"create portal config {config.id} (account default: {config.is_default})")
    return config


def ensure_webhook(url: str):
    for endpoint in stripe.WebhookEndpoint.list(limit=100).auto_paging_iter():
        if endpoint.url == url:
            missing = sorted(set(WEBHOOK_EVENTS) - set(endpoint.enabled_events))
            if missing and "*" not in endpoint.enabled_events:
                if DRY_RUN:
                    log(f"would add events {missing} to webhook {endpoint.id}")
                else:
                    stripe.WebhookEndpoint.modify(endpoint.id, enabled_events=sorted(set(endpoint.enabled_events) | set(WEBHOOK_EVENTS)))
                    log(f"update webhook {endpoint.id}: added {missing}")
            log(f"reuse  webhook {endpoint.id} (signing secret is only shown at creation;"
                " reveal it in Dashboard > Developers > Webhooks)")
            return None
    if DRY_RUN:
        log(f"would create webhook -> {url}")
        return None
    endpoint = stripe.WebhookEndpoint.create(url=url, enabled_events=WEBHOOK_EVENTS,
                                             description="Calimara supporter subscriptions and coffees")
    log(f"create webhook {endpoint.id} -> {url}")
    return endpoint.secret


def main() -> None:
    global DRY_RUN
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--webhook-url", help="Create/update a webhook endpoint for this URL (skip for local `stripe listen`).")
    parser.add_argument("--dry-run", action="store_true", help="Only report what would change.")
    args = parser.parse_args()
    DRY_RUN = args.dry_run

    stripe.api_key = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY")
    if not stripe.api_key:
        sys.exit("Set STRIPE_API_KEY (or STRIPE_SECRET_KEY).")
    log(f"mode: {'LIVE' if stripe.api_key.startswith(('sk_live', 'rk_live')) else 'test'}{' (dry run)' if DRY_RUN else ''}")

    prices = {key: ensure_price(key, match, name, amount, interval) for key, match, name, amount, interval, _ in ITEMS}
    portal = ensure_portal([prices[k] for k in ("trubadur", "cronicar", "rapsod") if prices[k] is not None])
    secret = ensure_webhook(args.webhook_url) if args.webhook_url else None

    print("# --- copy into .env ---")
    for key, _, _, _, _, env_name in ITEMS:
        if prices[key] is not None:
            print(f"{env_name}={prices[key].id}")
    if portal is not None:
        print(f"STRIPE_PORTAL_CONFIGURATION_ID={portal.id}")
    if secret:
        print(f"STRIPE_WEBHOOK_SECRET={secret}")


if __name__ == "__main__":
    main()
