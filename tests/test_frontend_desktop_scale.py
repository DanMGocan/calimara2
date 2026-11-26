import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def read(path: str) -> str:
    return (FRONTEND / path).read_text(encoding="utf-8")


def test_desktop_pointers_get_ninety_percent_page_zoom():
    styles = read("src/index.css")

    assert "--page-zoom: 1;" in styles
    assert re.search(
        r"@media screen and \(min-width: 1181px\) and \(hover: hover\) and \(pointer: fine\) \{\s*"
        r":root \{ --page-zoom: 0\.9; \}",
        styles,
    )
    assert re.search(r"html \{[^}]*zoom: var\(--page-zoom\);", styles)


def test_vite_compensates_viewport_units_for_page_zoom():
    config = read("vite.config.js")

    assert 'import viewportZoom from "./postcss-viewport-zoom.js";' in config
    assert "plugins: [viewportZoom()]" in config


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_viewport_unit_rewrite():
    samples = {
        "100vh": "calc(100vh / var(--page-zoom, 1))",
        "calc(100svh - var(--nav-h) - 28px)": "calc(calc(100svh / var(--page-zoom, 1)) - var(--nav-h) - 28px)",
        "clamp(30px, min(4.1vw, 6.8vh), 58px)": (
            "clamp(30px, min(calc(4.1vw / var(--page-zoom, 1)), calc(6.8vh / var(--page-zoom, 1))), 58px)"
        ),
        "min(780px, calc(100dvh - 64px))": "min(780px, calc(calc(100dvh / var(--page-zoom, 1)) - 64px))",
        "-.5vmin": "calc(-.5vmin / var(--page-zoom, 1))",
        # Already compensated values and non-viewport lengths are left alone.
        "calc(100vh / var(--page-zoom, 1))": "calc(100vh / var(--page-zoom, 1))",
        "12px 1.5rem": "12px 1.5rem",
        "var(--h1vh)": "var(--h1vh)",
    }
    script = (
        "import { divideViewportUnits } from './postcss-viewport-zoom.js';"
        "const input = JSON.parse(process.argv[1]);"
        "console.log(JSON.stringify(input.map(divideViewportUnits)));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, json.dumps(list(samples))],
        cwd=FRONTEND,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == list(samples.values())


def test_js_positioning_divides_window_pixels_by_css_zoom():
    zoom = read("src/app/zoom.js")
    layout = read("src/app/layout.jsx")
    editor = read("src/RichTextEditor.jsx")

    assert "export function cssZoomOf(element)" in zoom
    assert "element?.currentCSSZoom" in zoom

    assert "const zoom = cssZoomOf(tooltip);" in layout
    assert "const center = (rect.left + rect.width / 2) / zoom;" in layout
    assert "tooltip.style.top = `${Math.round(rect.bottom / zoom + 8)}px`;" in layout
    assert "const viewportWidth = window.innerWidth / zoom;" in layout
    assert "const viewportHeight = window.innerHeight / zoom;" in layout

    assert "const zoom = cssZoomOf(wrapper || editor.view.dom);" in editor
    assert "const rawLeft = (wrapperRect ? coords.left - wrapperRect.left : coords.left) / zoom;" in editor
