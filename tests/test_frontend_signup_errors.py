import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.schemas.users import PasswordRegisterRequest

ROOT = Path(__file__).resolve().parents[1]
CLIENT_JS = ROOT / "frontend" / "src" / "api" / "client.js"
AUTH_MODAL = ROOT / "frontend" / "src" / "app" / "auth-modal.jsx"


def _client_error_message(status: int, body: object) -> str:
    """Run the real api client against a stubbed fetch and return the thrown message."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = f"""
const {{ api }} = await import({json.dumps(CLIENT_JS.as_uri())});
globalThis.fetch = async () => new Response({json.dumps(json.dumps(body))}, {{
  status: {status},
  headers: {{ "content-type": "application/json" }}
}});
try {{
  await api.post("/api/autentificare/parola/inregistrare", {{}});
  console.log("NO ERROR");
}} catch (error) {{
  console.log(error.message);
}}
"""
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return result.stdout.strip()


def test_validation_error_list_is_shown_as_text_not_object():
    body = {
        "detail": [
            {
                "type": "string_too_short",
                "loc": ["body", "password"],
                "msg": "String should have at least 8 characters",
                "input": "short",
                "ctx": {"min_length": 8},
            }
        ]
    }
    message = _client_error_message(422, body)
    assert "[object Object]" not in message
    assert message == "String should have at least 8 characters"


def test_string_detail_is_passed_through():
    message = _client_error_message(400, {"detail": "Există deja un cont cu această adresă."})
    assert message == "Există deja un cont cu această adresă."


def test_signup_modal_checks_backend_password_minimum_before_submitting():
    source = AUTH_MODAL.read_text(encoding="utf-8")
    match = re.search(r"const MIN_SIGNUP_PASSWORD_LENGTH = (\d+);", source)
    assert match, "auth modal must define MIN_SIGNUP_PASSWORD_LENGTH"
    backend_min = next(
        meta.min_length
        for meta in PasswordRegisterRequest.model_fields["password"].metadata
        if hasattr(meta, "min_length")
    )
    assert int(match.group(1)) == backend_min
    register_body = source.split("const submitRegistration", 1)[1].split("const submitActivation", 1)[0]
    assert register_body.index("MIN_SIGNUP_PASSWORD_LENGTH") < register_body.index("registerWithPassword(")
