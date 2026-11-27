"""Regression guard: the test suite must never reach the real Brevo API."""

import os
from unittest.mock import patch

import pytest

from app import email_service, models


def test_production_email_settings_are_neutralised_in_tests():
    assert email_service.emails_enabled() is False
    assert os.getenv("BREVO_API_KEY") == ""


def test_brevo_send_refuses_without_network_call():
    email = models.EmailOutbox(
        recipient_email="contact@calimara.ro",
        recipient_name="guard",
        subject="guard",
        html_content="<p>guard</p>",
        text_content="guard",
    )
    with patch.object(email_service.httpx, "Client") as client:
        with pytest.raises(RuntimeError, match="BREVO_API_KEY is not configured"):
            email_service._send_with_brevo(email)
    client.assert_not_called()


def test_send_now_is_a_noop_even_when_a_test_enables_emails():
    # A test that turns emails on but forgets to mock Brevo still must not
    # send: with no API key the send fails locally before any HTTP request.
    with patch.dict(os.environ, {"EMAILS_ENABLED": "True"}), patch.object(
        email_service.httpx, "Client"
    ) as client:
        email = models.EmailOutbox(
            recipient_email="contact@calimara.ro",
            recipient_name="guard",
            subject="guard",
            html_content="<p>guard</p>",
            text_content="guard",
        )
        with pytest.raises(RuntimeError):
            email_service._send_with_brevo(email)
    client.assert_not_called()
