import asyncio
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth, crud, diacritics, email_service, main as app_main, models, schemas, text_formatting
from app.repositories import writing as writing_repository
from app.routers import auth_routes, writing_routes
from app.week_util import utcnow_naive


def _user(premium: bool = True) -> models.User:
    user = models.User(
        id=1,
        username="writer",
        email="writer@example.com",
        google_id="google-writer",
        premium_until=utcnow_naive() + timedelta(days=30) if premium else None,
        premium_tier="trubadur" if premium else "free",
        created_at=datetime(2026, 1, 31, 12, 0, 0),
    )
    return user


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        models.Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture(autouse=True)
def reset_diacritics_provider_cooldown(monkeypatch):
    monkeypatch.setattr(diacritics, "_provider_unavailable_until", 0.0)
    monkeypatch.setattr(diacritics, "_provider_unavailable_reason", "")


def _db_user(db, premium: bool = True, tier: str = "trubadur") -> models.User:
    user = models.User(
        username=f"writer-{tier}-{len(db.query(models.User).all())}",
        email=f"writer-{tier}-{len(db.query(models.User).all())}@example.com",
        google_id=f"google-{tier}-{len(db.query(models.User).all())}",
        premium_tier=tier if premium else "free",
        premium_until=utcnow_naive() + timedelta(days=30) if premium else None,
        premium_period_start=utcnow_naive() - timedelta(days=1) if premium else None,
        created_at=datetime(2026, 1, 31, 12, 0, 0),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _fake_response(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def _mark_diacritics_service_available(monkeypatch):
    monkeypatch.setattr(writing_routes.diacritics, "ensure_diacritics_service_available", lambda: None)
    monkeypatch.setattr(
        writing_routes.diacritics,
        "diacritics_service_status",
        lambda: {
            "service_available": True,
            "service_unavailable_reason": None,
            "service_retry_after_seconds": None,
        },
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


def test_add_diacritics_retries_once_after_invalid_ai_json(monkeypatch):
    calls = {"count": 0}

    def complete(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return _fake_response("nu este json")
        return _fake_response('{"title": null, "content": "Șapte țări"}')

    fake_client = SimpleNamespace(chat=SimpleNamespace(complete=complete))
    monkeypatch.setattr(diacritics, "DIACRITICS_ENABLED", True)
    monkeypatch.setattr(diacritics, "client", fake_client)

    result = diacritics.add_diacritics(kind="comment", title=None, content="Sapte tari")

    assert calls["count"] == 2
    assert result["content"] == "Șapte țări"
    assert result["changed"] is True


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


def test_format_post_content_uses_mistral_small_json_response(monkeypatch):
    captured = {}

    def complete_chat(**kwargs):
        captured.update(kwargs)
        return _fake_response(
            '{"category": "poezie", "content": "<p>primul vers<br>al doilea vers</p><p>strofa a doua</p>"}'
        )

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(complete=complete_chat)
    )
    monkeypatch.setattr(text_formatting, "AI_FORMATTING_ENABLED", True)
    monkeypatch.setattr(text_formatting, "AI_FORMATTING_MODEL", "mistral-small-latest")
    monkeypatch.setattr(text_formatting, "client", fake_client)

    result = text_formatting.format_post_content(
        category="proza_scurta",
        content="<p>primul vers\nal doilea vers\n\nstrofa a doua</p>",
    )

    assert result == {
        "category": "poezie",
        "content": "<p>primul vers<br>al doilea vers</p><p>strofa a doua</p>",
        "changed": True,
    }
    assert captured["model"] == "mistral-small-latest"


def test_format_post_content_rejects_invalid_ai_output(monkeypatch):
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(complete=lambda **kwargs: _fake_response("nu este json"))
    )
    monkeypatch.setattr(text_formatting, "AI_FORMATTING_ENABLED", True)
    monkeypatch.setattr(text_formatting, "client", fake_client)

    with pytest.raises(RuntimeError):
        text_formatting.format_post_content(category="poezie", content="<p>text valid</p>")


def test_writing_diacritics_endpoint_requires_login():
    with pytest.raises(HTTPException) as exc:
        auth.get_required_user(None)

    assert exc.value.status_code == 401


def test_auth_setup_diacritics_endpoint_uses_pending_session(monkeypatch):
    captured = {}

    def convert(**kwargs):
        captured.update(kwargs)
        return {
            "title": None,
            "content": "<p>Îmi place aici</p>",
            "changed": True,
        }

    monkeypatch.setattr(auth_routes.diacritics, "add_diacritics", convert)
    handler = getattr(auth_routes.add_setup_diacritics, "__wrapped__", auth_routes.add_setup_diacritics)

    response = handler(
        request=SimpleNamespace(session={"pending_auth": {"source": "invitation_password", "email": "nou@example.com"}}),
        body=schemas.DiacriticsRequest(kind="profile_description", content="<p>Imi place aici</p>"),
    )

    assert captured["kind"] == "profile_description"
    assert captured["content"] == "<p>Imi place aici</p>"
    assert response["content"] == "<p>Îmi place aici</p>"
    assert response["changed"] is True
    assert response["quota"] is None


def test_auth_setup_diacritics_endpoint_requires_pending_session():
    handler = getattr(auth_routes.add_setup_diacritics, "__wrapped__", auth_routes.add_setup_diacritics)

    with pytest.raises(HTTPException) as exc:
        handler(
            request=SimpleNamespace(session={}),
            body=schemas.DiacriticsRequest(kind="profile_description", content="<p>Imi place aici</p>"),
        )

    assert exc.value.status_code == 400
    assert "sesiune de configurare" in exc.value.detail


def test_validation_errors_with_value_error_context_stay_json_serializable():
    request = SimpleNamespace(
        method="POST",
        url=SimpleNamespace(path="/api/scriere/diacritice"),
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"user-agent": "pytest"},
    )
    exc = RequestValidationError([
        {
            "type": "value_error",
            "loc": ("body",),
            "msg": "Value error, Categoria este obligatorie pentru texte",
            "input": {"kind": "post", "content": "<p>fara diacritice</p>"},
            "ctx": {"error": ValueError("Categoria este obligatorie pentru texte")},
        }
    ])

    response = asyncio.run(app_main.validation_exception_handler(request, exc))
    payload = json.loads(response.body)

    assert response.status_code == 422
    assert payload["detail"][0]["ctx"]["error"] == "Categoria este obligatorie pentru texte"


def test_diacritics_quota_payload_uses_tiered_limits(db):
    free = _db_user(db, premium=False)
    trubadur = _db_user(db, premium=True, tier="trubadur")
    cronicar = _db_user(db, premium=True, tier="cronicar")
    rapsod = _db_user(db, premium=True, tier="rapsod")

    assert crud.diacritics_quota_payload(db, free)["limit"] == 15000
    assert crud.diacritics_quota_payload(db, trubadur)["limit"] == 60000
    assert crud.diacritics_quota_payload(db, cronicar)["limit"] == 120000
    assert crud.diacritics_quota_payload(db, rapsod)["limit"] == 180000


def test_diacritics_quota_payload_handles_missing_usage_table(db):
    user = _db_user(db, premium=True)
    db.execute(text("DROP TABLE diacritics_usage_events"))
    db.commit()

    quota = crud.diacritics_quota_payload(db, user)

    assert quota["limit"] == 60000
    assert quota["used"] == 0
    assert quota["remaining"] == 60000
    assert quota["can_request"] is False


def test_diacritics_quota_payload_expires_stale_pending_usage(db):
    user = _db_user(db, premium=True)
    period_start, period_end = crud.diacritics_quota_period_for_user(user)
    event = models.DiacriticsUsageEvent(
        user_id=user.id,
        kind="comment",
        character_count=100,
        quota_period_start=period_start,
        quota_period_end=period_end,
        status="pending",
        created_at=utcnow_naive() - timedelta(minutes=30),
    )
    db.add(event)
    db.commit()

    quota = crud.diacritics_quota_payload(db, user)

    db.refresh(event)
    assert event.status == "failed"
    assert quota["used"] == 0
    assert quota["remaining"] == 60000


def test_free_user_diacritics_period_is_anchored_to_signup_date(db, monkeypatch):
    user = _db_user(db, premium=False)
    monkeypatch.setattr(writing_repository, "utcnow_naive", lambda: datetime(2026, 3, 15, 10, 0, 0))
    start, end = crud.diacritics_quota_period_for_user(user)

    assert start == datetime(2026, 2, 28, 12, 0, 0)
    assert end == datetime(2026, 3, 31, 12, 0, 0)


def test_writing_diacritics_endpoint_returns_converted_text(db, monkeypatch):
    _mark_diacritics_service_available(monkeypatch)
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
        db=db,
        current_user=_db_user(db, premium=True),
    )

    assert response["title"] == "Orașul"
    assert response["content"] == "Șapte țări"
    assert response["changed"] is True
    assert response["quota"]["limit"] == 60000
    assert response["quota"]["used"] == 16


def test_writing_ai_formatting_endpoint_returns_formatted_post(db, monkeypatch):
    captured = {}

    def format_post(**kwargs):
        captured.update(kwargs)
        return {
            "category": "poezie",
            "content": "<p>vers unu<br>vers doi</p>",
            "changed": True,
        }

    monkeypatch.setattr(writing_routes.text_formatting, "format_post_content", format_post)
    handler = getattr(writing_routes.format_post_with_ai_api, "__wrapped__", writing_routes.format_post_with_ai_api)

    response = handler(
        request=SimpleNamespace(),
        body=schemas.PostFormatRequest(category="proza_scurta", content="<p>vers unu\nvers doi</p>"),
        current_user=_db_user(db, premium=False),
    )

    assert captured == {"category": "proza_scurta", "content": "<p>vers unu\nvers doi</p>"}
    assert response["category"] == "poezie"
    assert response["content"] == "<p>vers unu<br>vers doi</p>"
    assert response["changed"] is True


def test_writing_diacritics_endpoint_returns_profile_description(db, monkeypatch):
    _mark_diacritics_service_available(monkeypatch)
    captured = {}

    def convert(**kwargs):
        captured.update(kwargs)
        return {
            "title": None,
            "content": "<p>Sunt aici</p>",
            "changed": True,
        }

    monkeypatch.setattr(writing_routes.diacritics, "add_diacritics", convert)
    handler = getattr(writing_routes.add_diacritics_api, "__wrapped__", writing_routes.add_diacritics_api)

    response = handler(
        request=SimpleNamespace(),
        body=schemas.DiacriticsRequest(kind="profile_description", content="<p>Sunt aici</p>"),
        db=db,
        current_user=_db_user(db, premium=True),
    )

    assert captured["kind"] == "profile_description"
    assert captured["content"] == "<p>Sunt aici</p>"
    assert response["content"] == "<p>Sunt aici</p>"
    assert response["changed"] is True
    assert response["quota"]["used"] == 9


def test_writing_diacritics_endpoint_returns_private_message(db, monkeypatch):
    _mark_diacritics_service_available(monkeypatch)
    captured = {}

    def convert(**kwargs):
        captured.update(kwargs)
        return {
            "title": None,
            "content": "Fără diacritice",
            "changed": True,
        }

    monkeypatch.setattr(writing_routes.diacritics, "add_diacritics", convert)
    handler = getattr(writing_routes.add_diacritics_api, "__wrapped__", writing_routes.add_diacritics_api)

    response = handler(
        request=SimpleNamespace(),
        body=schemas.DiacriticsRequest(kind="private_message", content="Fara diacritice"),
        db=db,
        current_user=_db_user(db, premium=True),
    )

    assert captured["kind"] == "private_message"
    assert captured["content"] == "Fara diacritice"
    assert response["content"] == "Fără diacritice"
    assert response["changed"] is True
    assert response["quota"]["used"] == 15


def test_private_message_diacritics_rejects_over_message_limit():
    with pytest.raises(ValidationError):
        schemas.DiacriticsRequest(kind="private_message", content="x" * 2001)


def test_writing_diacritics_endpoint_allows_free_user_with_quota(db, monkeypatch):
    _mark_diacritics_service_available(monkeypatch)
    monkeypatch.setattr(
        writing_routes.diacritics,
        "add_diacritics",
        lambda **kwargs: {
            "title": None,
            "content": "Șapte țări",
            "changed": True,
        },
    )
    handler = getattr(writing_routes.add_diacritics_api, "__wrapped__", writing_routes.add_diacritics_api)

    response = handler(
        request=SimpleNamespace(),
        body=schemas.DiacriticsRequest(kind="comment", content="Sapte tari"),
        db=db,
        current_user=_db_user(db, premium=False),
    )

    assert response["content"] == "Șapte țări"
    assert response["quota"]["limit"] == 15000
    assert response["quota"]["used"] == 10


def test_writing_diacritics_endpoint_returns_theatre_payload(db, monkeypatch):
    _mark_diacritics_service_available(monkeypatch)
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
        db=db,
        current_user=_db_user(db, premium=True),
    )

    assert response["title"] == "Orașul"
    assert response["description"] == "Șapte țări"
    assert response["characters"] == [{"index": 0, "description": "Călător"}]
    assert response["changed"] is True
    assert response["quota"]["used"] == 23


def test_writing_diacritics_endpoint_rejects_over_quota_without_ai_call(db, monkeypatch):
    _mark_diacritics_service_available(monkeypatch)
    user = _db_user(db, premium=False)
    period_start, period_end = crud.diacritics_quota_period_for_user(user)
    db.add(
        models.DiacriticsUsageEvent(
            user_id=user.id,
            kind="comment",
            character_count=14995,
            quota_period_start=period_start,
            quota_period_end=period_end,
            status="succeeded",
        )
    )
    db.commit()
    called = False

    def convert(**kwargs):
        nonlocal called
        called = True
        return {"content": "Șapte țări", "changed": True}

    monkeypatch.setattr(writing_routes.diacritics, "add_diacritics", convert)
    handler = getattr(writing_routes.add_diacritics_api, "__wrapped__", writing_routes.add_diacritics_api)

    with pytest.raises(HTTPException) as exc:
        handler(
            request=SimpleNamespace(),
            body=schemas.DiacriticsRequest(kind="comment", content="Sapte tari"),
            db=db,
            current_user=user,
        )

    assert exc.value.status_code == 409
    assert "Disponibil: 5, cerut: 10" in exc.value.detail
    assert called is False


def test_writing_diacritics_endpoint_rejects_missing_usage_table_without_ai_call(db, monkeypatch):
    _mark_diacritics_service_available(monkeypatch)
    user = _db_user(db, premium=True)
    db.execute(text("DROP TABLE diacritics_usage_events"))
    db.commit()
    called = False

    def convert(**kwargs):
        nonlocal called
        called = True
        return {"content": "Șapte țări", "changed": True}

    monkeypatch.setattr(writing_routes.diacritics, "add_diacritics", convert)
    handler = getattr(writing_routes.add_diacritics_api, "__wrapped__", writing_routes.add_diacritics_api)

    with pytest.raises(HTTPException) as exc:
        handler(
            request=SimpleNamespace(),
            body=schemas.DiacriticsRequest(kind="comment", content="Sapte tari"),
            db=db,
            current_user=user,
        )

    assert exc.value.status_code == 503
    assert "Diacriticele sunt indisponibile" in exc.value.detail
    assert called is False


def test_writing_diacritics_endpoint_surfaces_service_errors(db, monkeypatch):
    _mark_diacritics_service_available(monkeypatch)

    def fail(**kwargs):
        raise RuntimeError("Serviciul AI nu este disponibil.")

    monkeypatch.setattr(writing_routes.diacritics, "add_diacritics", fail)
    handler = getattr(writing_routes.add_diacritics_api, "__wrapped__", writing_routes.add_diacritics_api)

    with pytest.raises(HTTPException) as exc:
        handler(
            request=SimpleNamespace(),
            body=schemas.DiacriticsRequest(kind="comment", content="fara diacritice"),
            db=db,
            current_user=_db_user(db, premium=True),
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == "Serviciul AI nu este disponibil."
    assert db.query(models.DiacriticsUsageEvent).one().status == "failed"
    alert = db.query(models.EmailOutbox).filter_by(email_type=email_service.EMAIL_TYPE_SYSTEM_ALERT).one()
    assert alert.recipient_email == "contact@calimara.ro"
    assert alert.extra_data["service"] == "Diacritice"


def test_writing_diacritics_endpoint_wraps_ai_transport_errors(db, monkeypatch):
    def timeout(**kwargs):
        raise TimeoutError("timed out")

    fake_client = SimpleNamespace(chat=SimpleNamespace(complete=timeout))
    monkeypatch.setattr(diacritics, "DIACRITICS_ENABLED", True)
    monkeypatch.setattr(diacritics, "client", fake_client)
    handler = getattr(writing_routes.add_diacritics_api, "__wrapped__", writing_routes.add_diacritics_api)
    user = _db_user(db, premium=True)

    with pytest.raises(HTTPException) as exc:
        handler(
            request=SimpleNamespace(),
            body=schemas.DiacriticsRequest(kind="comment", content="Sapte tari"),
            db=db,
            current_user=user,
        )

    assert exc.value.status_code == 503
    assert "temporar indisponibil" in exc.value.detail
    event = db.query(models.DiacriticsUsageEvent).one()
    assert event.status == "failed"
    assert "temporar indisponibil" in event.error_message
    assert crud.diacritics_quota_payload(db, user)["used"] == 0
    alert = db.query(models.EmailOutbox).filter_by(email_type=email_service.EMAIL_TYPE_SYSTEM_ALERT).one()
    assert "Conversia automată la diacritice" in alert.extra_data["summary"]


def test_diacritics_character_count_for_theatre_request():
    body = schemas.DiacriticsRequest(
        kind="theatre_play",
        title="Oras mare",
        description="Sapte tari",
        characters=[{"index": 0, "description": "Calator batran"}],
    )

    assert crud.diacritics_character_count_for_request(body) == 33
