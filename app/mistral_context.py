import json
import os
from collections.abc import Mapping, Sequence
from typing import Any


DEFAULT_MISTRAL_SMALL_4_CONTEXT_TOKENS = 256_000
DEFAULT_MISTRAL_CONTEXT_TOKENS = 32_768
DEFAULT_OUTPUT_RESERVE_TOKENS = 1_024
DEFAULT_SAFETY_MARGIN_TOKENS = 512


class MistralContextWindowExceeded(RuntimeError):
    """Raised before sending a Mistral request that is too large for the model."""

    def __init__(
        self,
        *,
        model: str,
        purpose: str,
        estimated_input_tokens: int,
        max_output_tokens: int,
        context_limit: int,
        safety_margin_tokens: int,
    ):
        self.model = model
        self.purpose = purpose
        self.estimated_input_tokens = estimated_input_tokens
        self.max_output_tokens = max_output_tokens
        self.context_limit = context_limit
        self.safety_margin_tokens = safety_margin_tokens
        available = max(0, context_limit - safety_margin_tokens)
        super().__init__(
            f"{purpose} exceeds {model} context window: estimated input "
            f"{estimated_input_tokens} tokens + output reserve {max_output_tokens} "
            f"> available {available} tokens."
        )


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def context_limit_for_model(model: str) -> int:
    normalized = (model or "").strip().lower()
    if not normalized:
        return _env_int("MISTRAL_CONTEXT_TOKENS", DEFAULT_MISTRAL_CONTEXT_TOKENS)

    exact_env_key = "MISTRAL_CONTEXT_TOKENS_" + "".join(
        char.upper() if char.isalnum() else "_"
        for char in normalized
    )
    exact_override = os.getenv(exact_env_key)
    if exact_override:
        return _env_int(exact_env_key, DEFAULT_MISTRAL_CONTEXT_TOKENS)

    if "mistral-small" in normalized:
        return _env_int(
            "MISTRAL_SMALL_CONTEXT_TOKENS",
            _env_int("MISTRAL_SMALL_4_CONTEXT_TOKENS", DEFAULT_MISTRAL_SMALL_4_CONTEXT_TOKENS),
        )
    if "mistral-moderation" in normalized:
        return _env_int("MISTRAL_MODERATION_CONTEXT_TOKENS", DEFAULT_MISTRAL_CONTEXT_TOKENS)
    if "mistral-large" in normalized:
        return _env_int("MISTRAL_LARGE_CONTEXT_TOKENS", 131_072)
    return _env_int("MISTRAL_CONTEXT_TOKENS", DEFAULT_MISTRAL_CONTEXT_TOKENS)


def estimate_token_upper_bound(value: Any) -> int:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    return len(text.encode("utf-8"))


def estimate_chat_input_tokens(messages: Sequence[Mapping[str, Any]]) -> int:
    message_overhead = _env_int("MISTRAL_MESSAGE_OVERHEAD_TOKENS", 16)
    base_overhead = _env_int("MISTRAL_CHAT_OVERHEAD_TOKENS", 8)
    payload_tokens = estimate_token_upper_bound({"messages": list(messages)})
    return payload_tokens + base_overhead + (message_overhead * len(messages))


def validate_chat_context(
    *,
    model: str,
    messages: Sequence[Mapping[str, Any]],
    max_output_tokens: int | None = None,
    purpose: str = "Mistral request",
) -> dict[str, int]:
    output_tokens = int(max_output_tokens or _env_int("MISTRAL_DEFAULT_OUTPUT_RESERVE_TOKENS", DEFAULT_OUTPUT_RESERVE_TOKENS))
    safety_margin = _env_int("MISTRAL_CONTEXT_SAFETY_MARGIN_TOKENS", DEFAULT_SAFETY_MARGIN_TOKENS)
    context_limit = context_limit_for_model(model)
    input_tokens = estimate_chat_input_tokens(messages)
    if input_tokens + output_tokens + safety_margin > context_limit:
        raise MistralContextWindowExceeded(
            model=model,
            purpose=purpose,
            estimated_input_tokens=input_tokens,
            max_output_tokens=output_tokens,
            context_limit=context_limit,
            safety_margin_tokens=safety_margin,
        )
    return {
        "estimated_input_tokens": input_tokens,
        "max_output_tokens": output_tokens,
        "context_limit": context_limit,
        "safety_margin_tokens": safety_margin,
    }


def validate_text_context(
    *,
    model: str,
    texts: Sequence[str],
    max_output_tokens: int | None = 0,
    purpose: str = "Mistral request",
) -> dict[str, int]:
    messages = [{"role": "user", "content": "\n\n".join(texts)}]
    return validate_chat_context(
        model=model,
        messages=messages,
        max_output_tokens=max_output_tokens,
        purpose=purpose,
    )
