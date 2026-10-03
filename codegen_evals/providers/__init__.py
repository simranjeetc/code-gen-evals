"""Provider registry and selection."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .. import config
from .base import (
    Provider,
    ProviderConfigError,
    ProviderError,
    extract_code,
    iter_fences,
)

PROVIDER_NAMES = (
    "mock",
    "opencode",
    "claude-code",
    "anthropic",
    "openai",
    "together",
)

_DEFAULT_MODELS: Dict[str, List[str]] = {
    "mock": list(config.MOCK_MODELS),
    "opencode": list(config.DEFAULT_MODEL_BANK),
    "claude-code": [config.DEFAULT_CLAUDE_CODE_MODEL],
    "anthropic": ["claude-sonnet-4-5"],
    "openai": ["gpt-4o"],
    "together": ["meta-llama/Llama-2-70b-chat-hf"],
}


def default_models(provider_name: str) -> List[str]:
    """The model bank to use when the caller does not name models."""
    try:
        return list(_DEFAULT_MODELS[provider_name])
    except KeyError:
        raise ProviderConfigError(
            f"unknown provider '{provider_name}'; expected one of {', '.join(PROVIDER_NAMES)}"
        ) from None


def build_provider(
    name: str,
    specs: Optional[Sequence[Any]] = None,
    temperature: float = config.DEFAULT_TEMPERATURE,
    timeout_s: float = config.DEFAULT_TIMEOUT_S,
    **kwargs: Any,
) -> Provider:
    """Construct a provider by name.

    ``specs`` is only used by the mock provider, which needs each spec's
    reference solution and required symbols to synthesise runnable candidates.
    """
    if name == "mock":
        from .mock import MockProvider

        references: Dict[str, str] = {}
        required: Dict[str, Sequence[str]] = {}
        for spec in specs or []:
            references[spec.id] = _reference_source(spec)
            required[spec.id] = list(spec.required_symbols)
        return MockProvider(
            references=references,
            required_symbols=required,
            skills=dict(config.MOCK_SKILLS),
            temperature=temperature,
            timeout_s=timeout_s,
        )

    if name == "opencode":
        from .opencode import OpenCodeProvider

        return OpenCodeProvider(temperature=temperature, timeout_s=timeout_s, **kwargs)

    if name == "claude-code":
        from .claude_code import ClaudeCodeProvider

        return ClaudeCodeProvider(temperature=temperature, timeout_s=timeout_s, **kwargs)

    if name in ("anthropic", "openai", "together"):
        from . import public_api

        provider_class = {
            "anthropic": public_api.AnthropicProvider,
            "openai": public_api.OpenAIProvider,
            "together": public_api.TogetherProvider,
        }[name]
        return provider_class(temperature=temperature, timeout_s=timeout_s, **kwargs)

    raise ProviderConfigError(
        f"unknown provider '{name}'; expected one of {', '.join(PROVIDER_NAMES)}"
    )


def _reference_source(spec: Any) -> str:
    from ..corpus import solution_source

    try:
        return solution_source(spec)
    except (OSError, ValueError):
        return ""


__all__ = [
    "Provider",
    "ProviderConfigError",
    "ProviderError",
    "PROVIDER_NAMES",
    "build_provider",
    "default_models",
    "extract_code",
    "iter_fences",
]
