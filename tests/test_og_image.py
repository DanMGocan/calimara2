"""Shared links use the 1200x630 preview image, and the server actually serves it."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_default_preview_image_everywhere():
    from app import seo

    assert seo.DEFAULT_IMAGE_PATH == "/og-image.jpg"
    index = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert 'property="og:image" content="https://calimara.ro/og-image.jpg"' in index
    assert 'name="twitter:image" content="https://calimara.ro/og-image.jpg"' in index
    assert 'const DEFAULT_IMAGE = "/og-image.jpg";' in (ROOT / "frontend/src/app/seo.js").read_text(encoding="utf-8")


def test_image_file_is_1200x630():
    from PIL import Image

    with Image.open(ROOT / "frontend/public/og-image.jpg") as image:
        assert image.size == (1200, 630)
        assert image.mode == "RGB"
    assert (ROOT / "frontend/public/og-image.jpg").stat().st_size < 300_000


def test_route_serves_jpeg_not_the_spa(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as main

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "og-image.jpg").write_bytes(b"\xff\xd8\xff fake jpeg")
    monkeypatch.setattr(main, "FRONTEND_DIST", str(dist))

    response = TestClient(main.app).get("/og-image.jpg", headers={"host": "lvh.me:8000"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert "max-age" in response.headers["cache-control"]
