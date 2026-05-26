from types import SimpleNamespace

import pytest

from app import diacritics, moderation
from app.mistral_context import MistralContextWindowExceeded, validate_chat_context


def test_mistral_context_guard_blocks_requests_over_model_window(monkeypatch):
    monkeypatch.setenv("MISTRAL_SMALL_CONTEXT_TOKENS", "120")
    monkeypatch.setenv("MISTRAL_CONTEXT_SAFETY_MARGIN_TOKENS", "10")

    with pytest.raises(MistralContextWindowExceeded) as exc:
        validate_chat_context(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": "x" * 200}],
            max_output_tokens=20,
            purpose="test",
        )

    assert exc.value.model == "mistral-small-latest"
    assert exc.value.max_output_tokens == 20
    assert exc.value.context_limit == 120


def test_mistral_context_guard_allows_requests_inside_budget(monkeypatch):
    monkeypatch.setenv("MISTRAL_SMALL_CONTEXT_TOKENS", "1000")
    monkeypatch.setenv("MISTRAL_CONTEXT_SAFETY_MARGIN_TOKENS", "10")

    estimate = validate_chat_context(
        model="mistral-small-2603",
        messages=[{"role": "user", "content": "text scurt"}],
        max_output_tokens=50,
        purpose="test",
    )

    assert estimate["context_limit"] == 1000
    assert estimate["estimated_input_tokens"] > 0


def test_diacritics_preflight_rejects_too_long_payload_before_client(monkeypatch):
    monkeypatch.setenv("MISTRAL_SMALL_CONTEXT_TOKENS", "220")
    monkeypatch.setenv("MISTRAL_CONTEXT_SAFETY_MARGIN_TOKENS", "10")
    monkeypatch.setattr(diacritics, "DIACRITICS_MODEL", "mistral-small-latest")
    monkeypatch.setattr(diacritics, "DIACRITICS_MAX_TOKENS", 80)

    with pytest.raises(MistralContextWindowExceeded):
        diacritics.validate_diacritics_request_context(
            title="Titlu",
            content="x" * 1000,
            kind="post",
        )


def test_moderation_llm_review_sets_output_budget(monkeypatch):
    captured = {}

    def complete(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"safe": true, "reason": "ok"}'))]
        )

    monkeypatch.setenv("MISTRAL_SMALL_CONTEXT_TOKENS", "10000")
    monkeypatch.setattr(moderation, "client", SimpleNamespace(chat=SimpleNamespace(complete=complete)))
    monkeypatch.setattr(moderation, "MODERATION_REVIEW_MODEL", "mistral-small-latest")
    monkeypatch.setattr(moderation, "MODERATION_REVIEW_MAX_TOKENS", 600)

    result = moderation.review_content_with_llm("Text", {"hate": 0.4}, {"profanity_detected": False})

    assert result["safe"] is True
    assert captured["max_tokens"] == 600
