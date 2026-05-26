from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_frontend(path: str) -> str:
    return (ROOT / "frontend" / "src" / path).read_text(encoding="utf-8")


def test_landing_shuffle_softens_footer_metric_transition():
    landing = read_frontend("routes/landing.jsx")
    app = read_frontend("App.jsx")
    post_actions = read_frontend("app/post-actions.jsx")
    styles = read_frontend("index.css")

    assert "const LANDING_POST_FADE_OUT_MS = 360" in landing
    assert "const LANDING_POST_SWAP_SETTLE_MS = 140" in landing
    assert "transitioning" in landing
    assert "footerPostActions.transitioning ? \"is-reader-switching\"" in app
    assert "className={`footer-post-tools ${footerPostActions.transitioning ? \"is-reader-switching\" : \"\"}`.trim()}" in app
    assert "function MetricCount" in post_actions
    assert "metric-count" in post_actions
    assert ".footer-post-actions-row.is-reader-switching" in styles
    assert ".footer-post-tools.is-reader-switching .metric-count" in styles
    assert "@keyframes metricCountEaseIn" in styles
    assert "font-variant-numeric: tabular-nums" in styles
