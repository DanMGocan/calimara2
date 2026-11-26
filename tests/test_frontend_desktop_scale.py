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


def test_page_zoom_is_switched_on_by_js_only_where_supported():
    styles = read("src/index.css")
    zoom = read("src/app/zoom.js")
    main = read("src/main.jsx")

    assert "--page-zoom: 1;" in styles
    assert re.search(r"html \{[^}]*zoom: var\(--page-zoom\);", styles)
    # The 0.9 value is no longer set by a CSS media query: browsers without currentCSSZoom
    # (or without CSS zoom) must keep the unscaled layout.
    assert "--page-zoom: 0.9" not in styles

    assert "export const PAGE_ZOOM = 0.9;" in zoom
    assert '"currentCSSZoom" in win.Element.prototype' in zoom
    assert main.index("installPageZoom();") < main.index("createRoot(")


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
        # Units match case-insensitively.
        "100VH": "calc(100VH / var(--page-zoom, 1))",
        # A value that mentions --page-zoom is compensated by hand: never divided twice.
        "calc((100vh - 64px) / var(--page-zoom, 1))": "calc((100vh - 64px) / var(--page-zoom, 1))",
        # ...but a similarly named property is not --page-zoom.
        "calc(100vh / var(--page-zoom-ratio))": "calc(calc(100vh / var(--page-zoom, 1)) / var(--page-zoom-ratio))",
        # Strings and url() arguments are never rewritten.
        "url(/img/100vw.png) 10vh": "url(/img/100vw.png) calc(10vh / var(--page-zoom, 1))",
        'url("/a b/50vh.png")': 'url("/a b/50vh.png")',
        '"10vh"': '"10vh"',
        "'5vw' 5vw": "'5vw' calc(5vw / var(--page-zoom, 1))",
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


def run_node(script: str, *args: str) -> str:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, *args],
        cwd=FRONTEND,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


@pytest.mark.skipif(
    shutil.which("node") is None or not (FRONTEND / "node_modules" / "postcss").exists(),
    reason="node or frontend dependencies are not installed",
)
def test_wide_media_queries_get_a_zoom_aware_twin():
    css = (
        "@media (min-width: 821px) and (max-width: 1536px) "
        "{ :root { --nav-h: 58px; } .nav, html body { padding: 1px; } }\n"
        "@media (max-width: 820px) { .nav { padding: 2px; } }\n"
        "@media (max-height: 700px) { .stage { height: 50vh; } }\n"
        "@media (max-height: 800px) { @media (min-width: 1300px) { .x { color: red; } } }\n"
        "@media print { .nav { display: none; } }\n"
    )
    script = (
        "import postcss from 'postcss';"
        "import viewportZoom from './postcss-viewport-zoom.js';"
        "const out = await postcss([viewportZoom()]).process(process.argv[1], { from: undefined });"
        "console.log(out.css);"
    )
    out = run_node(script, css)

    # The original query applies only without the scale, the twin (thresholds x 0.9) only with
    # it. :where() keeps specificity unchanged.
    assert (
        "@media (min-width: 821px) and (max-width: 1536px) "
        "{ :root:where(:not(.page-zoom-active)) { --nav-h: 58px; } "
        ":where(html:not(.page-zoom-active)) .nav, html:where(:not(.page-zoom-active)) body"
    ) in out
    assert (
        "@media (min-width: 738.9px) and (max-width: 1382.4px) "
        "{ :root:where(.page-zoom-active) { --nav-h: 58px; } "
        ":where(html.page-zoom-active) .nav, html:where(.page-zoom-active) body"
    ) in out
    # Width thresholds below the scale's 1181px trigger test the same either way.
    assert "@media (max-width: 820px) { .nav { padding: 2px; } }" in out
    assert "738px" not in out
    # Height queries always shift under zoom; viewport units inside are still compensated.
    assert (
        "@media (max-height: 630px) "
        "{ :where(html.page-zoom-active) .stage { height: calc(50vh / var(--page-zoom, 1)); } }"
    ) in out
    # Nested queries inside the twin are scaled too, and scoped once.
    assert (
        "@media (max-height: 720px) { @media (min-width: 1170px) "
        "{ :where(html.page-zoom-active) .x { color: red; } } }"
    ) in out
    assert "@media (min-width: 1300px) { :where(html:not(.page-zoom-active)) .x" in out
    assert "@media print { .nav { display: none; } }" in out


@pytest.mark.skipif(
    shutil.which("node") is None or not (FRONTEND / "node_modules" / "postcss").exists(),
    reason="node or frontend dependencies are not installed",
)
@pytest.mark.parametrize(
    "query",
    ["(width <= 1400px)", "(700px <= height)", "(max-width: 90em)", "(min-height: 40rem)"],
)
def test_unsupported_size_media_queries_fail_the_build(query):
    script = (
        "import postcss from 'postcss';"
        "import viewportZoom from './postcss-viewport-zoom.js';"
        "try { await postcss([viewportZoom()]).process(process.argv[1], { from: undefined }); console.log('ok'); }"
        "catch (error) { console.log(error.message); }"
    )
    out = run_node(script, f"@media {query} {{ .nav {{ padding: 1px; }} }}")
    assert "unsupported size media query" in out


@pytest.mark.skipif(
    shutil.which("node") is None or not (FRONTEND / "node_modules" / "postcss").exists(),
    reason="node or frontend dependencies are not installed",
)
def test_other_media_features_are_left_alone():
    script = (
        "import postcss from 'postcss';"
        "import viewportZoom from './postcss-viewport-zoom.js';"
        "const out = await postcss([viewportZoom()]).process(process.argv[1], { from: undefined });"
        "console.log(out.css);"
    )
    css = "@media (hover: hover) and (min-aspect-ratio: 16/9) and (orientation: landscape) { .a { color: red; } }"
    assert run_node(script, css).strip() == css


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_install_page_zoom_follows_support_and_the_desktop_query():
    script = """
import { installPageZoom, PAGE_ZOOM_CHANGE_EVENT } from './src/app/zoom.js';
function fakeWindow({ supported, matches }) {
  const classes = new Set(); const style = new Map(); const listeners = []; let events = 0;
  const winListeners = {};
  const query = { matches, addEventListener: (_, fn) => listeners.push(fn), removeEventListener() {} };
  function Element() {}
  Element.prototype = supported ? { currentCSSZoom: 1 } : {};
  const win = {
    Element,
    Event: class { constructor(type) { this.type = type; } },
    matchMedia: () => query,
    dispatchEvent: (e) => { if (e.type === PAGE_ZOOM_CHANGE_EVENT) events += 1; },
    addEventListener: (type, fn) => { winListeners[type] = fn; },
    fire: (type) => winListeners[type](),
    document: { documentElement: {
      classList: { toggle: (c, on) => (on ? classes.add(c) : classes.delete(c)) },
      style: { setProperty: (k, v) => style.set(k, v), removeProperty: (k) => style.delete(k) },
    } },
  };
  const state = () => ({ active: classes.has('page-zoom-active'), zoom: style.get('--page-zoom') ?? null, events });
  return { win, query, listeners, state };
}
const results = {};
let f = fakeWindow({ supported: false, matches: true });
installPageZoom(f.win); results.unsupported = f.state();
f = fakeWindow({ supported: true, matches: true });
installPageZoom(f.win); results.desktop = f.state();
f.win.fire('beforeprint'); results.printing = f.state();
f.win.fire('afterprint'); results.afterPrint = f.state();
f.query.matches = false; f.listeners.forEach((fn) => fn()); results.pointerRemoved = f.state();
console.log(JSON.stringify(results));
"""
    results = json.loads(run_node(script))

    assert results["unsupported"] == {"active": False, "zoom": None, "events": 0}
    assert results["desktop"] == {"active": True, "zoom": "0.9", "events": 1}
    assert results["printing"] == {"active": False, "zoom": None, "events": 2}
    assert results["afterPrint"] == {"active": True, "zoom": "0.9", "events": 3}
    assert results["pointerRemoved"] == {"active": False, "zoom": None, "events": 4}
    assert re.search(r"@media print \{\s*/\*[^*]*\*/\s*:root \{ --page-zoom: 1 !important; \}", read("src/index.css"))


def test_background_shapes_remeasure_when_page_zoom_changes():
    layout = read("src/app/layout.jsx")

    assert "window.addEventListener(PAGE_ZOOM_CHANGE_EVENT, handleResize);" in layout
    assert "window.removeEventListener(PAGE_ZOOM_CHANGE_EVENT, handleResize);" in layout
