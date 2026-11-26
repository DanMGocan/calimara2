import os
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret")

from app import models, seo


def _db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    return engine, db


def _request(path: str, *, username: str | None = None):
    return SimpleNamespace(
        url=SimpleNamespace(path=path),
        state=SimpleNamespace(username=username),
    )


def _user(db, username="seoauthor"):
    user = models.User(
        username=username,
        email=f"{username}@example.com",
        google_id=f"google-{username}",
        subtitle="<p>Autor de poezie și proză scurtă.</p>",
        avatar_seed=f"{username}-seed",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _post(db, user, title="Poem cu SEO", slug="poem-cu-seo", status="approved"):
    post = models.Post(
        user_id=user.id,
        title=title,
        slug=slug,
        content="<p>Un text literar cu suficiente detalii pentru descrierea din căutare.</p>",
        category="poezie",
        moderation_status=status,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def test_sitemap_lists_public_content_and_skips_private_routes():
    engine, db = _db_session()
    try:
        user = _user(db)
        post = _post(db, user)
        _post(db, user, title="Text pending", slug="text-pending", status="pending")
        series = models.Series(owner_id=user.id, title="Serie publică", slug="serie-publica", description="Descriere serie")
        db.add(series)
        db.flush()
        db.add(models.SeriesPost(series_id=series.id, post_id=post.id, position=1))
        db.add(models.TheatrePlay(creator_id=user.id, title="Piesă publică", slug="piesa-publica", description="Descriere piesă", status="active"))
        db.add(models.ForumThread(author_id=user.id, section="poezie", title="Discuție publică", slug="discutie-publica", content="<p>Discuție aprobată.</p>", moderation_status="approved"))
        db.commit()

        sitemap = seo.build_sitemap_xml(db)

        assert "https://calimara.ro/" in sitemap
        assert "https://seoauthor.calimara.ro/" in sitemap
        assert "https://seoauthor.calimara.ro/toate-operele" in sitemap
        assert f"https://seoauthor.calimara.ro/{post.slug}" in sitemap
        assert "https://calimara.ro/serii/serie-publica" in sitemap
        assert "https://calimara.ro/teatru/piesa-publica" in sitemap
        assert "/discutii" not in sitemap
        assert "text-pending" not in sitemap
        assert "/cluburi" not in sitemap
        assert "/stafeta" not in sitemap
    finally:
        db.close()
        models.Base.metadata.drop_all(engine)
        engine.dispose()


def test_page_metadata_uses_author_subdomain_post_data_and_noindexes_private_pages():
    engine, db = _db_session()
    try:
        user = _user(db)
        post = _post(db, user)

        post_meta = seo.build_page_metadata(db, _request(f"/{post.slug}", username=user.username))
        private_meta = seo.build_page_metadata(db, _request("/panou"))
        missing_meta = seo.build_page_metadata(db, _request("/nu-exista"))

        assert post_meta.title == "Poem cu SEO de @seoauthor | călimara.ro"
        assert post_meta.canonical_url == "https://seoauthor.calimara.ro/poem-cu-seo"
        assert post_meta.og_type == "article"
        assert post_meta.json_ld[0]["@type"] == "CreativeWork"
        assert not post_meta.noindex
        assert private_meta.noindex
        assert private_meta.robots == "noindex, nofollow"
        assert missing_meta.noindex
    finally:
        db.close()
        models.Base.metadata.drop_all(engine)
        engine.dispose()


def test_render_index_html_replaces_default_seo_tags():
    metadata = seo.PageMetadata(
        title="Titlu SEO",
        description="Descriere SEO",
        canonical_url="https://calimara.ro/text",
        image_url="https://calimara.ro/favicon.png",
        og_type="article",
        json_ld=[{"@context": "https://schema.org", "@type": "CreativeWork", "name": "Titlu SEO"}],
    )
    html = """
    <html><head>
      <title>Vechi</title>
      <meta name="description" content="vechi" data-seo="description" />
      <link rel="canonical" href="https://old.example" data-seo="canonical" />
    </head><body></body></html>
    """

    rendered = seo.render_index_html(html, metadata)

    assert "<title>Titlu SEO</title>" in rendered
    assert 'content="Descriere SEO"' in rendered
    assert 'rel="canonical" href="https://calimara.ro/text"' in rendered
    assert "https://old.example" not in rendered
    assert 'type="application/ld+json"' in rendered
    assert rendered.count('name="description"') == 1


def test_robots_txt_advertises_sitemap_without_blocking_public_rendering_apis():
    robots = seo.build_robots_txt()
    lines = robots.splitlines()

    assert "Sitemap: https://calimara.ro/sitemap.xml" in robots
    assert "Allow: /" in robots
    assert "Disallow: /api/admin/" in robots
    assert "Disallow: /api/" not in lines


def test_main_serves_robots_and_sitemap_endpoints():
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    engine, db = _db_session()
    try:
        user = _user(db, "routeauthor")
        post = _post(db, user, title="Route SEO", slug="route-seo")

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            client = TestClient(app)
            robots = client.get("/robots.txt", headers={"host": "calimara.ro"})
            sitemap = client.get("/sitemap.xml", headers={"host": "calimara.ro"})
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert robots.status_code == 200
        assert "Sitemap: https://calimara.ro/sitemap.xml" in robots.text
        assert sitemap.status_code == 200
        assert "application/xml" in sitemap.headers["content-type"]
        assert f"https://routeauthor.calimara.ro/{post.slug}" in sitemap.text
    finally:
        db.close()
        models.Base.metadata.drop_all(engine)
        engine.dispose()
