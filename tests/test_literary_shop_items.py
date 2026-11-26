import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

from app import crud, models
from app.repositories.economy import DEFAULT_SHOP_ITEMS

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ITEMS_DIR = ROOT / "frontend" / "public" / "assets" / "items" / "profile_badge"
DIST_ITEMS_DIR = ROOT / "frontend" / "dist" / "assets" / "items" / "profile_badge"
PREPARE_SCRIPT = ROOT / "scripts" / "prepare_art_asset.py"
MIGRATION_FILE = ROOT / "migrations" / "20261126_literary_shop_items.sql"
SCHEMA_FILE = ROOT / "schema.sql"

NEW_SLUGS = [
    "sicriul-de-plumb-al-lui-bacovia",
    "dintele-de-balena-al-lui-marin-sorescu",
    "portretul-veronicai-al-lui-mihai-eminescu",
]


def test_literary_shop_item_pngs_exist_and_pass_style_validator():
    for slug in NEW_SLUGS:
        png_path = PUBLIC_ITEMS_DIR / f"{slug}.png"
        assert png_path.is_file(), f"Missing PNG asset: {png_path}"
        result = subprocess.run(
            [sys.executable, str(PREPARE_SCRIPT), "--check", str(png_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"Asset check failed for {slug}: {result.stderr}\n{result.stdout}"


def test_default_shop_items_include_literary_artefacts():
    by_slug = {item["slug"]: item for item in DEFAULT_SHOP_ITEMS}
    for slug in NEW_SLUGS:
        assert slug in by_slug, f"Missing {slug} from DEFAULT_SHOP_ITEMS"
        item = by_slug[slug]
        assert item["slot"] == "profile_badge"
        assert item["price"] > 0
        assert item["asset_url"] == f"/assets/items/profile_badge/{slug}.png"


def test_seed_default_shop_items_is_idempotent():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        crud.seed_default_shop_items(db)
        crud.seed_default_shop_items(db)
        items = db.query(models.ShopItem).all()
        assert len(items) == len(DEFAULT_SHOP_ITEMS)
        seeded = {item.slug: item for item in items}
        for slug in NEW_SLUGS:
            assert seeded[slug].asset_url == f"/assets/items/profile_badge/{slug}.png"
    finally:
        db.close()
        models.Base.metadata.drop_all(engine)
        engine.dispose()


def test_schema_and_migration_register_literary_shop_items_idempotently():
    migration_sql = MIGRATION_FILE.read_text(encoding="utf-8")
    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    assert "ON CONFLICT (slug) DO NOTHING" in migration_sql
    for slug in NEW_SLUGS:
        expected_url = f"/assets/items/profile_badge/{slug}.png"
        assert slug in migration_sql and expected_url in migration_sql
        assert slug in schema_sql and expected_url in schema_sql


def test_built_dist_includes_literary_shop_item_pngs():
    if not (ROOT / "frontend" / "dist").is_dir():
        return
    for slug in NEW_SLUGS:
        assert (DIST_ITEMS_DIR / f"{slug}.png").is_file(), f"Built dist missing {slug}.png"
