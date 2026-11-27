"""Shared test setup.

Tests must never send real email. The app calls ``load_dotenv()`` on import,
and on this machine that finds the production ``.env`` (EMAILS_ENABLED=True and
a real BREVO_API_KEY), even from a worktree. Without this guard, the smoke test
for ``/api/admin/email/test-notification`` emailed contact@calimara.ro on every
run, and auth/invitation tests tried to mail @example.com addresses via Brevo.

The variables are set here, before any ``app`` module is imported, because
``load_dotenv()`` never overrides variables that already exist. The autouse
fixture re-applies them for each test in case a test changed ``os.environ``
directly. Tests that need the send path enable it themselves and mock
``email_service._send_with_brevo``.
"""

import os

import pytest

NO_REAL_EMAIL_ENV = {
    "EMAILS_ENABLED": "False",
    "BREVO_API_KEY": "",
}

os.environ.update(NO_REAL_EMAIL_ENV)


@pytest.fixture(autouse=True)
def _no_real_email(monkeypatch):
    for key, value in NO_REAL_EMAIL_ENV.items():
        monkeypatch.setenv(key, value)
