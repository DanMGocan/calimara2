import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret")

from app import models, seo

ROOT = Path(__file__).resolve().parents[1]
ROUTER_SOURCE = (ROOT / "frontend" / "src" / "app" / "router.jsx").read_text(encoding="utf-8")


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    yield session
    session.close()
    engine.dispose()


def _request(path, username=None):
    return SimpleNamespace(url=SimpleNamespace(path=path), state=SimpleNamespace(username=username))


def _user(db, username="autor"):
    user = models.User(username=username, email=f"{username}@example.com", google_id=f"g-{username}")
    db.add(user)
    db.commit()
    return user


def _post(db, user, slug="text", status="approved"):
    post = models.Post(user_id=user.id, title=slug, slug=slug, content="<p>text</p>", category="poezie", moderation_status=status)
    db.add(post)
    db.commit()
    return post


def _router_sections():
    sub_start = ROUTER_SOURCE.index("if (userFromHost) {")
    main_start = ROUTER_SOURCE.index('if (path === "/") return { name: "landing" }')
    return ROUTER_SOURCE[sub_start:main_start], ROUTER_SOURCE[main_start:]


def test_every_main_domain_frontend_route_is_not_a_404(db):
    _, main_section = _router_sections()
    exact = set(re.findall(r'path === "([^"]+)"', main_section))
    prefixes = set(re.findall(r'path\.startsWith\("([^"]+)"\)', main_section))
    assert exact and prefixes
    # Slug routes for content looked up in the DB (series/theatre/forum) 404 only when the slug is missing.
    db_backed = {"/serii/", "/teatru/", "/discutii/"}
    wrongly_404 = [p for p in exact if seo.build_page_metadata(db, _request(p)).not_found]
    wrongly_404 += [p + "x" for p in prefixes - db_backed if seo.build_page_metadata(db, _request(p + "x")).not_found]
    assert wrongly_404 == []


def test_every_subdomain_frontend_route_is_not_a_404(db):
    _user(db, "autor")
    sub_section, _ = _router_sections()
    exact = set(re.findall(r'path === "([^"]+)"', sub_section))
    assert "/panou" in exact and "/profil" in exact
    wrongly_404 = [p for p in exact if seo.build_page_metadata(db, _request(p, "autor")).not_found]
    assert wrongly_404 == []


@pytest.mark.parametrize("path", ["/nu-exista", "/panou/extra", "/serii/lipsa", "/teatru/lipsa", "/discutii/lipsa", "/serii"])
def test_unknown_or_missing_main_pages_are_404(db, path):
    assert seo.build_page_metadata(db, _request(path)).not_found


def test_subdomain_missing_author_and_post_are_404_but_pending_post_is_not(db):
    user = _user(db, "autor")
    _post(db, user, slug="publicat")
    _post(db, user, slug="in-asteptare", status="pending")

    assert seo.build_page_metadata(db, _request("/", "fantoma")).not_found
    assert seo.build_page_metadata(db, _request("/lipsa", "autor")).not_found
    assert not seo.build_page_metadata(db, _request("/publicat", "autor")).not_found
    assert not seo.build_page_metadata(db, _request("/in-asteptare", "autor")).not_found


def test_react_shell_returns_404_status_and_marker(db, tmp_path, monkeypatch):
    from app import main as app_main

    (tmp_path / "index.html").write_text("<html><head><title>x</title></head><body><div id=\"root\"></div></body></html>")
    monkeypatch.setattr(app_main, "FRONTEND_DIST", str(tmp_path))

    missing = app_main._react_index_response(request=_request("/nu-exista"), db=db)
    assert missing.status_code == 404
    assert app_main.NOT_FOUND_MARKER.encode() in missing.body

    found = app_main._react_index_response(request=_request("/premium"), db=db)
    assert found.status_code == 200
    assert app_main.NOT_FOUND_MARKER.encode() not in found.body


def test_post_with_comments_likes_and_feature_can_be_deleted(db):
    author = _user(db, "autor")
    reader = _user(db, "cititor")
    post = _post(db, author)
    db.add_all([
        models.Comment(post_id=post.id, user_id=reader.id, content="frumos", moderation_status="approved"),
        models.Like(post_id=post.id, user_id=reader.id),
    ])
    db.commit()
    post_id = post.id

    db.expire_all()
    loaded = db.get(models.Post, post_id)
    assert loaded.comments and loaded.likes  # loaded children, like the real delete endpoint
    db.delete(loaded)
    db.commit()

    assert db.get(models.Post, post_id) is None
    assert db.query(models.Comment).filter_by(post_id=post_id).count() == 0
    assert db.query(models.Like).filter_by(post_id=post_id).count() == 0
