import os

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret")

from app.main import app
from app.routers import shop_routes

LOCKED_ROUTES = {
    ("POST", "/api/magazin/obiecte/{item_id}/cumpara"),
    ("POST", "/api/inventar/echipeaza"),
    ("DELETE", "/api/inventar/echipate/{slot}"),
}


def _routes_with_lock():
    found = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if any(dep.call is shop_routes.require_shop_open for dep in route.dependant.dependencies):
            for method in route.methods - {"HEAD", "OPTIONS"}:
                found.add((method, route.path))
    return found


def test_only_shop_write_routes_are_locked():
    # Reads (/api/magazin/eu, public inventory) and admin shop management stay open.
    assert _routes_with_lock() == LOCKED_ROUTES


def test_lock_rejects_with_423_and_development_message(monkeypatch):
    monkeypatch.setattr(shop_routes, "SHOP_ACTIONS_LOCKED", True)
    with pytest.raises(HTTPException) as exc:
        shop_routes.require_shop_open()
    assert exc.value.status_code == 423
    assert exc.value.detail.startswith("În dezvoltare.")
    assert "aduni gologani" in exc.value.detail


def test_lock_can_be_lifted(monkeypatch):
    monkeypatch.setattr(shop_routes, "SHOP_ACTIONS_LOCKED", False)
    assert shop_routes.require_shop_open() is None
