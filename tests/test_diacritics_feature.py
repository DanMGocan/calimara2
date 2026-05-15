from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import auth, diacritics, models, schemas
from app.routers import writing_routes
from app.week_util import utcnow_naive


def _user(premium: bool = True) -> models.User:
    user = models.User(
        id=1,
        username="writer",
        email="writer@example.com",
        google_id="google-writer",
        premium_until=utcnow_naive() + timedelta(days=30) if premium else None,
        premium_tier="trubadur" if premium else "free",
    )
    return user


def _fake_response(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_add_diacritics_uses_ai_json_response(monkeypatch):
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            complete=lambda **kwargs: _fake_response(
                '{"title": "Șarpele din oraș", "content": "Într-o zi\\nșapte țări"}'
            )
        )
    )
    monkeypatch.setattr(diacritics, "DIACRITICS_ENABLED", True)
    monkeypatch.setattr(diacritics, "client", fake_client)

    result = diacritics.add_diacritics(
        kind="post",
        title="Sarpele din oras",
        content="Intr-o zi\nsapte tari",
    )

    assert result == {
        "title": "Șarpele din oraș",
        "content": "Într-o zi\nșapte țări",
        "changed": True,
    }


def test_add_diacritics_rejects_invalid_ai_output(monkeypatch):
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(complete=lambda **kwargs: _fake_response("nu este json"))
    )
    monkeypatch.setattr(diacritics, "DIACRITICS_ENABLED", True)
    monkeypatch.setattr(diacritics, "client", fake_client)

    with pytest.raises(RuntimeError):
        diacritics.add_diacritics(kind="comment", title=None, content="fara diacritice")


def test_add_theatre_play_diacritics_uses_structured_response(monkeypatch):
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            complete=lambda **kwargs: _fake_response(
                '{"title": "Orașul", "description": "Șapte țări", "characters": [{"index": 0, "description": "Călător bătrân"}]}'
            )
        )
    )
    monkeypatch.setattr(diacritics, "DIACRITICS_ENABLED", True)
    monkeypatch.setattr(diacritics, "client", fake_client)

    result = diacritics.add_theatre_play_diacritics(
        title="Orasul",
        description="Sapte tari",
        characters=[{"index": 0, "description": "Calator batran"}],
    )

    assert result == {
        "title": "Orașul",
        "description": "Șapte țări",
        "characters": [{"index": 0, "description": "Călător bătrân"}],
        "changed": True,
    }


def test_writing_diacritics_endpoint_requires_premium(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        auth.require_premium_user(_user(premium=False))

    assert exc.value.status_code == 403


def test_writing_diacritics_endpoint_returns_converted_text(monkeypatch):
    monkeypatch.setattr(
        writing_routes.diacritics,
        "add_diacritics",
        lambda **kwargs: {
            "title": "Orașul",
            "content": "Șapte țări",
            "changed": True,
        },
    )
    handler = getattr(writing_routes.add_diacritics_api, "__wrapped__", writing_routes.add_diacritics_api)

    response = handler(
        request=SimpleNamespace(),
        body=schemas.DiacriticsRequest(kind="post", title="Orasul", category="poezie", content="Sapte tari"),
        current_user=_user(premium=True),
    )

    assert response == {
        "title": "Orașul",
        "content": "Șapte țări",
        "changed": True,
    }


def test_writing_diacritics_endpoint_returns_theatre_payload(monkeypatch):
    monkeypatch.setattr(
        writing_routes.diacritics,
        "add_theatre_play_diacritics",
        lambda **kwargs: {
            "title": "Orașul",
            "description": "Șapte țări",
            "characters": [{"index": 0, "description": "Călător"}],
            "changed": True,
        },
    )
    handler = getattr(writing_routes.add_diacritics_api, "__wrapped__", writing_routes.add_diacritics_api)

    response = handler(
        request=SimpleNamespace(),
        body=schemas.DiacriticsRequest(
            kind="theatre_play",
            title="Orasul",
            description="Sapte tari",
            characters=[{"index": 0, "description": "Calator"}],
        ),
        current_user=_user(premium=True),
    )

    assert response == {
        "title": "Orașul",
        "description": "Șapte țări",
        "characters": [{"index": 0, "description": "Călător"}],
        "changed": True,
    }


def test_writing_diacritics_endpoint_surfaces_service_errors(monkeypatch):
    def fail(**kwargs):
        raise RuntimeError("Serviciul AI nu este disponibil.")

    monkeypatch.setattr(writing_routes.diacritics, "add_diacritics", fail)
    handler = getattr(writing_routes.add_diacritics_api, "__wrapped__", writing_routes.add_diacritics_api)

    with pytest.raises(HTTPException) as exc:
        handler(
            request=SimpleNamespace(),
            body=schemas.DiacriticsRequest(kind="comment", content="fara diacritice"),
            current_user=_user(premium=True),
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == "Serviciul AI nu este disponibil."
