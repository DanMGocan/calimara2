"""The site does not use em dashes, and public copy does not advertise AI."""

import re
from pathlib import Path

from app import ai_critic

ROOT = Path(__file__).resolve().parents[1]
EM_DASH = "—"
TEXT_SUFFIXES = {".py", ".js", ".jsx", ".css", ".html", ".sql", ".md", ".json", ".txt"}
SCANNED = ["app", "frontend/src", "frontend/index.html", "migrations", "scripts", "design", "schema.sql", "static"]

# Admin-only screens may name the moderation and critic services.
ADMIN_ONLY = {"frontend/src/routes/admin.jsx", "frontend/src/routes/docs.jsx"}
AI_WORD = re.compile(r"\b(AI|IA|Mistral|Anthropic|Claude)\b")


def _files(entry: str):
    path = ROOT / entry
    if path.is_file():
        yield path
    elif path.is_dir():
        for child in path.rglob("*"):
            if child.is_file() and child.suffix in TEXT_SUFFIXES and "node_modules" not in child.parts:
                yield child


def test_no_em_dashes_in_app_sources():
    offenders = []
    for entry in SCANNED:
        for path in _files(entry):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if EM_DASH in text:
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_public_frontend_copy_does_not_mention_ai():
    offenders = []
    for path in _files("frontend/src"):
        rel = str(path.relative_to(ROOT))
        if rel in ADMIN_ONLY:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if AI_WORD.search(line):
                offenders.append(f"{rel}:{number}")
    assert offenders == []


def test_user_facing_service_errors_do_not_mention_ai():
    for rel in ["app/diacritics.py", "app/text_formatting.py"]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "Serviciul AI" not in text
        assert "Răspunsul AI" not in text
        assert "cu AI" not in text
    for rel in ["app/routers/writing_routes.py", "app/routers/auth_routes.py"]:
        assert "modelul AI" not in (ROOT / rel).read_text(encoding="utf-8")


def test_critique_output_has_em_dashes_replaced():
    assert ai_critic._strip_long_dashes(f"Imaginea e vie {EM_DASH} finalul slăbește.") == "Imaginea e vie, finalul slăbește."
    assert ai_critic._strip_long_dashes(f"Ritm{EM_DASH}bun") == "Ritm, bun"
    assert EM_DASH not in ai_critic.CRITIC_PROMPT
