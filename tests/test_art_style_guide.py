import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART_STYLE_DOC = ROOT / "design" / "art-style.md"
DESIGN_DOC = ROOT / "design" / "design.md"
CANONICAL_REF = ROOT / "design" / "assets" / "style-reference-ink-wash.png"
PREPARE_SCRIPT = ROOT / "scripts" / "prepare_art_asset.py"
ADMIN_ROUTE = ROOT / "frontend" / "src" / "routes" / "admin.jsx"


def test_art_style_document_contains_required_specifications():
    assert ART_STYLE_DOC.is_file(), "design/art-style.md must exist"
    text = ART_STYLE_DOC.read_text(encoding="utf-8")

    for required in (
        "Tuș și laviu sepia",
        "style-reference-ink-wash.png",
        "#B84A2A",
        "#362A1D",
        "#EEE0C7",
        "profile_badge",
        "costume",
        "frame",
        "background",
        "scripts/prepare_art_asset.py",
        "Master Prompt Template",
        "Anti-Patterns",
        "Pre-Commit Quality Assurance Checklist",
    ):
        assert required in text, f"Missing expected section/token in design/art-style.md: {required}"


def test_design_system_cross_references_art_style_guide():
    text = DESIGN_DOC.read_text(encoding="utf-8")
    assert "design/art-style.md" in text


def test_canonical_reference_asset_passes_validator():
    assert CANONICAL_REF.is_file(), "Canonical style reference asset must exist"
    assert PREPARE_SCRIPT.is_file(), "scripts/prepare_art_asset.py must exist"
    result = subprocess.run(
        [sys.executable, str(PREPARE_SCRIPT), "--check", str(CANONICAL_REF)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Validator failed: {result.stderr}\n{result.stdout}"


def test_admin_dashboard_marks_ink_wash_as_approved():
    text = ADMIN_ROUTE.read_text(encoding="utf-8")
    assert "Stil aprobat" in text
    assert "approved: true" in text
