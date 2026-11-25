import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET_KEY", "test-secret")

from fastapi import HTTPException

from app import admin, integrations_guide

APP_DIR = Path(__file__).resolve().parents[1] / "app"
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend" / "src"
SECRET_VALUE = "super-secret-value-should-never-leak-123"


def _source_text() -> str:
    parts = [p.read_text(encoding="utf-8") for p in APP_DIR.rglob("*.py") if p.name != "integrations_guide.py"]
    parts += [p.read_text(encoding="utf-8") for p in FRONTEND_DIR.rglob("*.js*")]
    parts.append((APP_DIR.parent / "run.py").read_text(encoding="utf-8"))
    return "\n".join(parts)


def _all_var_names():
    for item in integrations_guide.INTEGRATIONS:
        for var in item["env"]:
            yield var["name"]
        yield from item["flags"]
        yield from item.get("backend_vars", [])


def test_every_listed_variable_is_used_by_the_app():
    source = _source_text()
    google_sdk_vars = {"GOOGLE_APPLICATION_CREDENTIALS"}  # read by the Google client libraries
    missing = [
        name for name in _all_var_names()
        if name not in google_sdk_vars and not re.search(rf"\b{name}\b", source)
    ]
    assert missing == []


def test_status_never_contains_values(monkeypatch):
    for name in _all_var_names():
        monkeypatch.setenv(name, SECRET_VALUE)
    payload = integrations_guide.integrations_status()
    assert SECRET_VALUE not in repr(payload)
    assert all(var["is_set"] for item in payload["integrations"] for var in item["env"])


def test_status_classification(monkeypatch):
    for name in _all_var_names():
        monkeypatch.delenv(name, raising=False)
    by_key = {i["key"]: i for i in integrations_guide.integrations_status()["integrations"]}
    assert by_key["mistral"]["status"] == "not_configured"

    monkeypatch.setenv("MODERATION_ENABLED", "True")
    by_key = {i["key"]: i for i in integrations_guide.integrations_status()["integrations"]}
    assert by_key["mistral"]["status"] == "incomplete"

    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    by_key = {i["key"]: i for i in integrations_guide.integrations_status()["integrations"]}
    assert by_key["mistral"]["status"] == "active"

    monkeypatch.setenv("MODERATION_ENABLED", "False")
    by_key = {i["key"]: i for i in integrations_guide.integrations_status()["integrations"]}
    assert by_key["mistral"]["status"] == "ready"


def test_google_audio_requires_credentials_file(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDIO_ENABLED", "True")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(tmp_path / "missing.json"))
    item = {i["key"]: i for i in integrations_guide.integrations_status()["integrations"]}["google_cloud_audio"]
    assert item["status"] == "incomplete"
    creds = tmp_path / "creds.json"
    creds.write_text("{}")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(creds))
    item = {i["key"]: i for i in integrations_guide.integrations_status()["integrations"]}["google_cloud_audio"]
    assert item["status"] == "active"


def test_endpoint_is_admin_only():
    from app.main import app

    route = next(r for r in app.routes if getattr(r, "path", "") == "/api/admin/integrations")
    dependency_calls = {dep.call for dep in route.dependant.dependencies}
    assert admin.require_admin in dependency_calls

    with pytest.raises(HTTPException) as unauthenticated:
        admin.require_admin(None)
    assert unauthenticated.value.status_code == 401

    class NonAdmin:
        is_admin = False
        email = "reader@example.com"

    with pytest.raises(HTTPException) as forbidden:
        admin.require_admin(NonAdmin())
    assert forbidden.value.status_code == 403
