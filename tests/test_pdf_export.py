import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

from app import models, pdf_exporter
from app.routers import api_pages, series_routes


class DummyRequest:
    def __init__(self, host="calimara.ro", scheme="https"):
        self.headers = {"host": host}
        self.url = SimpleNamespace(scheme=scheme)


class PdfExportTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        models.Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def make_user(self, username="author"):
        user = models.User(
            username=username,
            email=f"{username}@example.com",
            google_id=f"google-{username}",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def make_post(self, user, slug, *, title=None, status="approved"):
        post = models.Post(
            user_id=user.id,
            title=title or slug.replace("-", " ").title(),
            slug=slug,
            content="<p>Primul rand.</p><p>Al doilea rand.</p>",
            category="poezie",
            moderation_status=status,
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def make_series(self, owner, slug="test-series"):
        series = models.Series(
            owner_id=owner.id,
            title="Test Series",
            slug=slug,
            description="Descriere serie",
        )
        self.db.add(series)
        self.db.commit()
        self.db.refresh(series)
        return series

    def add_series_post(self, series, post, *, position=1):
        entry = models.SeriesPost(
            series_id=series.id,
            post_id=post.id,
            position=position,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def test_post_pdf_endpoint_returns_downloadable_pdf_response(self):
        author = self.make_user("poet")
        post = self.make_post(author, "poem-title")

        with patch.object(pdf_exporter, "render_post_pdf", return_value=b"%PDF-post") as renderer:
            response = api_pages.post_pdf_download(
                request=DummyRequest(host="calimara.ro"),
                username=author.username,
                slug=post.slug,
                db=self.db,
            )

        self.assertEqual(response.media_type, "application/pdf")
        self.assertEqual(response.body, b"%PDF-post")
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertIn("poem-title.pdf", response.headers["content-disposition"])
        self.assertEqual(renderer.call_args.kwargs["page_url"], "https://poet.calimara.ro/poem-title")

    def test_post_pdf_endpoint_hides_unapproved_posts(self):
        author = self.make_user("poet")
        post = self.make_post(author, "pending-title", status="pending")

        with self.assertRaises(HTTPException) as context:
            api_pages.post_pdf_download(
                request=DummyRequest(),
                username=author.username,
                slug=post.slug,
                db=self.db,
            )

        self.assertEqual(context.exception.status_code, 404)

    def test_series_pdf_endpoint_exports_only_public_approved_posts(self):
        owner = self.make_user("owner")
        series = self.make_series(owner, "public-series")
        accepted = self.make_post(owner, "accepted-poem")
        pending_post = self.make_post(owner, "pending-poem", status="pending")
        self.add_series_post(series, accepted, position=1)
        self.add_series_post(series, pending_post, position=2)

        with patch.object(pdf_exporter, "render_series_pdf", return_value=b"%PDF-series") as renderer:
            response = series_routes.series_pdf_download(
                request=DummyRequest(host="calimara.ro"),
                slug=series.slug,
                db=self.db,
            )

        exported_entries = renderer.call_args.kwargs["entries"]
        self.assertEqual([entry.post.slug for entry in exported_entries], ["accepted-poem"])
        self.assertEqual(response.media_type, "application/pdf")
        self.assertEqual(response.body, b"%PDF-series")
        self.assertIn("serie-public-series.pdf", response.headers["content-disposition"])

    def test_pdf_html_sanitizes_unsafe_post_content(self):
        html = pdf_exporter.build_post_pdf_html(
            title="Titlu",
            author="autor",
            content='<p>Text</p><script>alert(1)</script><img src=x><strong onclick="bad()">bold</strong>',
            page_url="https://autor.calimara.ro/titlu",
            category_label="Poezie",
        )

        self.assertIn("călimara.ro", html)
        self.assertIn("https://autor.calimara.ro/titlu", html)
        self.assertIn("<strong>bold</strong>", html)
        self.assertNotIn("<script", html)
        self.assertNotIn("alert(1)", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("onclick", html)

    def test_weasyprint_renderer_produces_pdf_bytes(self):
        pdf = pdf_exporter.render_html_to_pdf(
            "<!doctype html><html><body><h1>Calimara PDF</h1></body></html>"
        )

        self.assertTrue(pdf.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
