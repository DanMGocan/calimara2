"""Stripe Checkout asks customers to accept the terms when STRIPE_REQUIRE_TERMS is on."""

from unittest.mock import patch

import pytest

from app import stripe_service


class _Session:
    url = "https://checkout.stripe.test/s"


def test_off_by_default(monkeypatch):
    monkeypatch.delenv("STRIPE_REQUIRE_TERMS", raising=False)
    assert stripe_service.terms_consent_params("subscription") == {}


@pytest.mark.parametrize("kind", ["subscription", "coffee"])
def test_required_checkbox_with_terms_link(monkeypatch, kind):
    monkeypatch.setenv("STRIPE_REQUIRE_TERMS", "true")
    monkeypatch.setenv("MAIN_DOMAIN", "calimara.ro")
    monkeypatch.setenv("PUBLIC_SCHEME", "https")

    params = stripe_service.terms_consent_params(kind)

    assert params["consent_collection"] == {"terms_of_service": "required"}
    message = params["custom_text"]["terms_of_service_acceptance"]["message"]
    assert "[Termenii și condițiile](https://calimara.ro/termeni)" in message
    assert "14 zile" in message
    assert len(message) <= 1200  # Stripe's limit for custom text
    assert "—" not in message
    if kind == "subscription":
        assert "înceapă imediat" in message and "reînnoiește lunar" in message


def test_both_checkouts_send_the_consent(monkeypatch):
    monkeypatch.setenv("STRIPE_REQUIRE_TERMS", "true")
    monkeypatch.setenv("STRIPE_PRICE_ID_CAFEA", "price_cafea")
    with patch.object(stripe_service, "ensure_enabled"), \
            patch.object(stripe_service, "price_id_for_tier", return_value="price_rapsod"), \
            patch.object(stripe_service.stripe.checkout.Session, "create", return_value=_Session()) as create:
        stripe_service.create_checkout_session("cus_1", 7, tier="rapsod")
        subscription = create.call_args.kwargs
        stripe_service.create_coffee_checkout_session(2, user_id=7)
        coffee = create.call_args.kwargs

    for kwargs in (subscription, coffee):
        assert kwargs["consent_collection"] == {"terms_of_service": "required"}
        assert "terms_of_service_acceptance" in kwargs["custom_text"]
    assert subscription["mode"] == "subscription" and coffee["mode"] == "payment"


def test_checkouts_unchanged_when_off(monkeypatch):
    monkeypatch.setenv("STRIPE_REQUIRE_TERMS", "false")
    monkeypatch.setenv("STRIPE_PRICE_ID_CAFEA", "price_cafea")
    with patch.object(stripe_service, "ensure_enabled"), \
            patch.object(stripe_service, "price_id_for_tier", return_value="price_rapsod"), \
            patch.object(stripe_service.stripe.checkout.Session, "create", return_value=_Session()) as create:
        stripe_service.create_checkout_session("cus_1", 7, tier="rapsod")
        assert "consent_collection" not in create.call_args.kwargs
        stripe_service.create_coffee_checkout_session(1)
        assert "consent_collection" not in create.call_args.kwargs
