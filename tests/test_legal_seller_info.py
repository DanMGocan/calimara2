"""The terms and privacy pages identify the seller and the refund policy."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGAL = (ROOT / "frontend/src/routes/legal.jsx").read_text(encoding="utf-8")


def test_seller_identity_and_address():
    assert 'const OPERATOR_ADDRESS = "11 College Court, Portobello, Dublin, Irlanda";' in LEGAL
    assert "Daniel Mihai, persoană fizică" in LEGAL
    assert "operatorul datelor tale" in LEGAL
    assert "Adresa poștală: ${OPERATOR_ADDRESS}" in LEGAL
    assert "operatorul este Călimara" not in LEGAL


def test_refund_and_renewal_terms():
    assert "Rambursare în 14 zile" in LEGAL
    assert "în cel mult 14 zile de la cerere" in LEGAL
    assert "se reînnoiesc automat până când le anulezi" in LEGAL
    assert "ceri ca serviciul să înceapă imediat" in LEGAL


def test_law_authority_and_providers():
    assert "guvernați de legea din Irlanda" in LEGAL
    assert "Data Protection Commission din Irlanda" in LEGAL
    for provider in ("Contabo", "Cloudflare", "Stripe (Irlanda)", "Brevo (Franța)", "Google Cloud"):
        assert provider in LEGAL, provider
    assert "Cadrului UE-SUA privind protecția datelor" in LEGAL


def test_public_copy_rules():
    assert "—" not in LEGAL  # no em dashes
    assert not re.search(r"\b(AI|IA|Mistral|Anthropic|Claude)\b", LEGAL)
