from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ECONOMY = ROOT / "frontend" / "src" / "routes" / "economy.jsx"
CSS = ROOT / "frontend" / "src" / "index.css"

MESSAGE = "Tu continuă să aduni gologani și noi ne asigurăm că ai pe ce îi cheltui!"


def test_shop_and_inventory_views_are_locked_behind_development_overlay():
    source = ECONOMY.read_text(encoding="utf-8")

    assert "function DevelopmentOverlay" in source
    assert "În dezvoltare." in source
    assert MESSAGE in source
    # The wrapped content must not be clickable or focusable.
    assert "inert" in source
    assert 'aria-hidden="true"' in source

    # Magazin, own Inventar and public Inventar views are each wrapped.
    for view in ("function ShopView", "function InventoryView", "function PublicInventoryView"):
        start = source.index(view)
        end = source.find("\nfunction ", start + 1)
        body = source[start:end if end != -1 else len(source)]
        assert body.count("<DevelopmentOverlay>") == 1, view
        assert body.count("</DevelopmentOverlay>") == 1, view


def test_development_overlay_styles_exist():
    css = CSS.read_text(encoding="utf-8")

    for selector in (".dev-overlay-wrap", ".dev-overlay-content", ".dev-overlay {", ".dev-overlay-card", ".dev-overlay-text"):
        assert selector in css
    assert "pointer-events: none" in css
