"""Authors can delete the audio of their own posts from the dashboard."""

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import audio_service, auth, crud, models
from app.database import get_db

ROOT = Path(__file__).resolve().parents[1]
PERIOD = (datetime(2026, 11, 1), datetime(2026, 12, 1))


@pytest.fixture
def audio_root(tmp_path, monkeypatch):
    root = tmp_path / "audio"
    root.mkdir()
    monkeypatch.setenv("AUDIO_LOCAL_DIR", str(root))
    return root


@pytest.fixture
def Session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    models.Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autocommit=False, autoflush=False)
    engine.dispose()


@pytest.fixture
def db(Session):
    session = Session()
    yield session
    session.close()


def _user(db, name):
    user = models.User(username=name, email=f"{name}@x.t", google_id=f"g-{name}")
    db.add(user)
    db.commit()
    return user


def _post(db, user, slug="t"):
    post = models.Post(user_id=user.id, title="Titlu", slug=f"{user.username}-{slug}", content="c", moderation_status="approved")
    db.add(post)
    db.commit()
    return post


def _audio(db, post, root, *, source="tts", status="ready", key=None, chars=500, requester=None):
    key = key or f"posts/{post.id}/audio/{source}-{status}.mp3"
    audio = models.PostAudio(
        post_id=post.id, source=source, status=status, storage_backend="local", storage_key=key,
        tts_character_count=chars if source == "tts" else 0,
        requester_user_id=requester if requester is not None else post.user_id,
        quota_period_start=PERIOD[0], quota_period_end=PERIOD[1],
    )
    db.add(audio)
    db.commit()
    path = root / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"mp3")
    return audio, path


def test_delete_removes_files_and_audio(db, audio_root):
    ana = _user(db, "ana")
    post = _post(db, ana)
    _, tts_path = _audio(db, post, audio_root)
    _, author_path = _audio(db, post, audio_root, source="author")

    removed = audio_service.delete_post_audio_for_author(db, post)

    assert removed == 2
    assert not tts_path.exists() and not author_path.exists()
    assert crud.get_best_audio_for_post(db, post.id) is None
    assert crud.get_latest_audio_for_post(db, post.id) is None
    summary = audio_service.post_audio_summary(db, post)
    assert summary["audio_available"] is False and summary["audio_status"] == "missing"
    assert summary["author_audio_status"] == "missing"


def test_deleted_tts_still_counts_toward_quota(db, audio_root):
    ana = _user(db, "ana")
    post = _post(db, ana)
    _audio(db, post, audio_root, chars=700)
    before = crud.get_user_audio_tts_character_usage(db, ana.id, *PERIOD)

    audio_service.delete_post_audio_for_author(db, post)

    assert before == 700
    assert crud.get_user_audio_tts_character_usage(db, ana.id, *PERIOD) == 700
    row = db.query(models.PostAudio).one()
    assert row.deleted_at is not None and row.status == "cancelled" and row.storage_key is None


def test_failed_audio_is_removed_without_using_quota(db, audio_root):
    ana = _user(db, "ana")
    post = _post(db, ana)
    _audio(db, post, audio_root, status="failed", chars=900)

    audio_service.delete_post_audio_for_author(db, post)

    assert db.query(models.PostAudio).count() == 0
    assert crud.get_user_audio_tts_character_usage(db, ana.id, *PERIOD) == 0


def test_new_tts_can_be_requested_after_delete(db, audio_root):
    ana = _user(db, "ana")
    post = _post(db, ana)
    _audio(db, post, audio_root)

    audio_service.delete_post_audio_for_author(db, post)

    assert crud.get_active_or_ready_tts_for_post(db, post.id) is None


@pytest.mark.parametrize("status", ["pending", "processing"])
def test_audio_in_progress_blocks_delete(db, audio_root, status):
    ana = _user(db, "ana")
    post = _post(db, ana)
    _, ready_path = _audio(db, post, audio_root, source="author")
    _audio(db, post, audio_root, status=status)

    with pytest.raises(audio_service.AudioDeleteBusy):
        audio_service.delete_post_audio_for_author(db, post)
    assert ready_path.exists()
    assert db.query(models.PostAudio).filter(models.PostAudio.deleted_at.isnot(None)).count() == 0


def test_other_posts_audio_is_untouched(db, audio_root):
    ana = _user(db, "ana")
    first, second = _post(db, ana, "a"), _post(db, ana, "b")
    _audio(db, first, audio_root)
    _, other_path = _audio(db, second, audio_root)

    audio_service.delete_post_audio_for_author(db, first)

    assert other_path.exists()
    assert crud.get_best_audio_for_post(db, second.id) is not None


@pytest.fixture
def client(Session):
    from fastapi.testclient import TestClient
    import app.main as main

    def _db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    main.app.dependency_overrides[get_db] = _db
    yield main.app, TestClient(main.app)
    main.app.dependency_overrides.pop(get_db, None)
    main.app.dependency_overrides.pop(auth.get_required_user, None)


def test_route_deletes_only_for_the_owner(client, db, audio_root):
    app, http = client
    ana, ion = _user(db, "ana"), _user(db, "ion")
    post = _post(db, ana)
    _, path = _audio(db, post, audio_root)
    post_id = post.id
    for user in (ana, ion):
        db.refresh(user)
    db.expunge_all()

    app.dependency_overrides[auth.get_required_user] = lambda: ion
    denied = http.delete(f"/api/postari/{post_id}/audio", headers={"host": "lvh.me:8000"})
    assert denied.status_code == 404 and path.exists()

    app.dependency_overrides[auth.get_required_user] = lambda: ana
    allowed = http.delete(f"/api/postari/{post_id}/audio", headers={"host": "lvh.me:8000"})
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["removed"] == 1 and allowed.json()["audio_available"] is False
    assert not path.exists()


def test_route_reports_busy_audio(client, db, audio_root):
    app, http = client
    ana = _user(db, "ana")
    post = _post(db, ana)
    _audio(db, post, audio_root, status="processing")
    post_id = post.id
    db.refresh(ana)
    db.expunge_all()

    app.dependency_overrides[auth.get_required_user] = lambda: ana
    response = http.delete(f"/api/postari/{post_id}/audio", headers={"host": "lvh.me:8000"})

    assert response.status_code == 409


def test_dashboard_offers_delete_audio():
    source = (ROOT / "frontend/src/routes/dashboard.jsx").read_text()
    api = (ROOT / "frontend/src/api/audio.js").read_text()

    assert "export function deletePostAudio(postId)" in api
    assert "/api/postari/${encodeURIComponent(postId)}/audio" in api
    assert "deletePostAudio(post.id)" in source
    assert "Șterge audio" in source
    assert "window.confirm" in source and "nu se recuperează" in source


def test_migration_adds_deleted_at_idempotently():
    sql = (ROOT / "migrations/20261127_post_audio_deleted_at.sql").read_text()
    schema = (ROOT / "schema.sql").read_text()

    assert "ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP" in sql
    assert "DROP" not in sql.upper()
    assert "deleted_at TIMESTAMP," in schema
