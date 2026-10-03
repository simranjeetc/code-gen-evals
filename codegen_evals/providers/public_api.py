"""Optional public-API providers (Anthropic, OpenAI, Together).

These are inactive unless their credential is present in the environment.
Every class raises :class:`ProviderConfigError` naming the missing variable at
construction time, so selecting an unconfigured backend fails loudly instead of
silently falling back.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional, Tuple

from .base import Provider, ProviderConfigError


def _post_json(
    url: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    timeout_s: float,
    opener: Optional[Callable] = None,
) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    if opener is None:
        opener = urllib.request.urlopen
    try:
        with opener(request, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:300]
        raise ProviderConfigError(f"HTTP {error.code} from {url}: {detail}") from error
    except urllib.error.URLError as error:
        raise ProviderConfigError(f"network error calling {url}: {error.reason}") from error


class _HttpProvider(Provider):
    """Shared plumbing for credential-gated HTTP providers."""

    env_var = ""
    url = ""
    default_model = ""

    def __init__(self, temperature: float = 0.0, timeout_s: float = 120.0, opener=None):
        super().__init__(temperature=temperature, timeout_s=timeout_s)
        self.api_key = os.environ.get(self.env_var, "").strip()
        if not self.api_key:
            raise ProviderConfigError(
                f"{self.name} provider requires the {self.env_var} environment variable"
            )
        self._opener = opener

    def _payload(self, prompt: str, model_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def _headers(self) -> Dict[str, str]:
        raise NotImplementedError

    def _extract_text(self, data: Dict[str, Any]) -> str:
        raise NotImplementedError

    def _invoke(
        self, prompt: str, model_id: str, spec_id: str = ""
    ) -> Tuple[str, Dict[str, Any]]:
        model = model_id or self.default_model
        data = _post_json(
            self.url,
            self._payload(prompt, model),
            self._headers(),
            self.timeout_s,
            opener=self._opener,
        )
        return self._extract_text(data), {"model": model, "provider": self.name}


class AnthropicProvider(_HttpProvider):
    name = "anthropic"
    env_var = "ANTHROPIC_API_KEY"
    url = "https://api.anthropic.com/v1/messages"
    default_model = "claude-sonnet-4-5"

    def _headers(self) -> Dict[str, str]:
        return {
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

    def _payload(self, prompt: str, model_id: str) -> Dict[str, Any]:
        return {
            "model": model_id,
            "max_tokens": 4096,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

    def _extract_text(self, data: Dict[str, Any]) -> str:
        blocks = data.get("content") or []
        return "".join(block.get("text", "") for block in blocks if block.get("type") == "text")


class OpenAIProvider(_HttpProvider):
    name = "openai"
    env_var = "OPENAI_API_KEY"
    url = "https://api.openai.com/v1/chat/completions"
    default_model = "gpt-4o"

    def _headers(self) -> Dict[str, str]:
        return {
            "content-type": "application/json",
            "authorization": f"Bearer {self.api_key}",
        }

    def _payload(self, prompt: str, model_id: str) -> Dict[str, Any]:
        return {
            "model": model_id,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

    def _extract_text(self, data: Dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            return ""
        return (choices[0].get("message") or {}).get("content", "") or ""


class TogetherProvider(_HttpProvider):
    name = "together"
    env_var = "TOGETHER_API_KEY"
    url = "https://api.together.xyz/v1/chat/completions"
    default_model = "meta-llama/Llama-2-70b-chat-hf"

    def _headers(self) -> Dict[str, str]:
        return {
            "content-type": "application/json",
            "authorization": f"Bearer {self.api_key}",
        }

    def _payload(self, prompt: str, model_id: str) -> Dict[str, Any]:
        return {
            "model": model_id,
            "temperature": self.temperature,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }

    def _extract_text(self, data: Dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            return ""
        return (choices[0].get("message") or {}).get("content", "") or ""
