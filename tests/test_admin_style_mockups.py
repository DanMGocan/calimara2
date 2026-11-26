from pathlib import Path
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_MOCKUPS_DIR = ROOT / "frontend" / "public" / "assets" / "style-mockups"
DIST_MOCKUPS_DIR = ROOT / "frontend" / "dist" / "assets" / "style-mockups"
ADMIN_ROUTE = ROOT / "frontend" / "src" / "routes" / "admin.jsx"

EXPECTED_FILES = [
    "manuscript-oil.png",
    "manuscript-ink-wash.png",
    "manuscript-watercolor.png",
    "manuscript-gouache.png",
]


def test_style_mockup_assets_are_transparent_rgba_pngs():
    for filename in EXPECTED_FILES:
        asset_path = PUBLIC_MOCKUPS_DIR / filename
        assert asset_path.is_file(), f"Missing mockup asset: {asset_path}"

        with Image.open(asset_path) as image:
            assert image.format == "PNG"
            assert image.mode == "RGBA"
            width, height = image.size
            assert width >= 512 and height >= 512

            # Corners must be fully transparent
            for corner in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
                assert image.getpixel(corner)[3] == 0, f"Corner {corner} is not transparent in {filename}"

            alpha_band = image.getchannel("A")
            alpha_values = list(alpha_band.get_flattened_data())
            transparent_pixels = sum(1 for value in alpha_values if value == 0)
            opaque_pixels = sum(1 for value in alpha_values if value > 200)
            total_pixels = width * height
            assert transparent_pixels / total_pixels >= 0.30, f"Expected transparent background in {filename}"
            assert opaque_pixels / total_pixels >= 0.20, f"Expected visible foreground item in {filename}"


def test_admin_dashboard_wires_style_mockups_tab_and_assets():
    source = ADMIN_ROUTE.read_text(encoding="utf-8")
    assert '"artStyles"' in source
    assert "Stil vizual" in source
    for filename in EXPECTED_FILES:
        assert f"/assets/style-mockups/{filename}" in source


def test_built_frontend_dist_includes_style_mockups():
    if not DIST_MOCKUPS_DIR.parent.is_dir():
        return
    for filename in EXPECTED_FILES:
        assert (DIST_MOCKUPS_DIR / filename).is_file(), f"Built dist missing {filename}"
