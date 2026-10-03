"""Provider base contract, code extraction, and shared errors."""

from __future__ import annotations

import time
from typing import Any, Dict, Iterator, List, Optional, Tuple

from ..models import Generation

PYTHON_TAGS = frozenset({"python", "python3", "python2", "py", "py3"})


class ProviderError(Exception):
    """Base class for provider failures."""


class ProviderConfigError(ProviderError):
    """A provider is selected but not usable (missing credential, binary, ...)."""


def iter_fences(text: str) -> Iterator[Tuple[str, str]]:
    """Yield ``(info_string, body)`` for each fenced block.

    An unterminated fence runs to the end of the text, because models do
    sometimes omit the closing fence and the code is still usable.
    """
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped.startswith("```"):
            index += 1
            continue
        info = stripped[3:].strip()
        body: List[str] = []
        index += 1
        while index < len(lines) and not lines[index].strip().startswith("```"):
            body.append(lines[index])
            index += 1
        if index < len(lines):
            index += 1  # consume the closing fence
        yield info, "\n".join(body)


def _tag(info: str) -> str:
    parts = info.split()
    return parts[0].lower() if parts else ""


def extract_code(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract candidate code.

    Prefers the first Python-tagged fence; falls back to the first untagged
    fence. Returns ``(code, language)`` or ``(None, None)`` when there is
    nothing usable. This is the only place that decides "did the model give us
    code?".
    """
    if not text:
        return None, None

    fallback: Optional[str] = None
    for info, body in iter_fences(text):
        tag = _tag(info)
        if tag in PYTHON_TAGS:
            return _normalise(body), (tag or "python")
        if tag == "" and fallback is None:
            fallback = body

    if fallback is not None:
        return _normalise(fallback), ""

    return None, None


def _normalise(body: str) -> str:
    return body if body.endswith("\n") or body == "" else body + "\n"


class Provider:
    """Common contract: prompt + model id in, a :class:`Generation` out.

    Subclasses implement :meth:`_invoke`. Every failure mode is captured on the
    returned ``Generation`` rather than raised, so one bad call cannot abort a
    whole run.
    """

    name = "base"

    def __init__(self, temperature: float = 0.0, timeout_s: float = 120.0):
        self.temperature = temperature
        self.timeout_s = timeout_s

    def _invoke(self, prompt: str, model_id: str, spec_id: str = "") -> Tuple[str, Dict[str, Any]]:
        raise NotImplementedError

    def generate(self, prompt: str, model_id: str, spec_id: str = "") -> Generation:
        generation = Generation(
            model_id=model_id,
            provider=self.name,
            spec_id=spec_id,
            params={"temperature": self.temperature},
        )
        started = time.monotonic()
        try:
            raw_text, params = self._invoke(prompt, model_id, spec_id)
        except Exception as error:  # noqa: BLE001 - contained by design
            generation.duration_s = time.monotonic() - started
            generation.error = f"{type(error).__name__}: {error}"
            return generation

        generation.duration_s = time.monotonic() - started
        generation.raw_text = raw_text
        if params:
            generation.params.update(params)

        code, language = extract_code(raw_text)
        if code is None:
            generation.extracted = False
            generation.error = "no fenced code block found in response"
            return generation

        generation.code = code
        generation.extracted = True
        generation.params["language"] = language
        return generation

    def generate_text(self, prompt: str, model_id: str, spec_id: str = "") -> Generation:
        """Like :meth:`generate` but without requiring a code block.

        Used for judge calls, whose contract is raw JSON rather than code.
        Extraction is deliberately not attempted here: a judge response that
        happens to contain a fenced block would otherwise be reinterpreted as a
        candidate solution.
        """
        generation = Generation(
            model_id=model_id,
            provider=self.name,
            spec_id=spec_id,
            params={"temperature": self.temperature, "raw_text": True},
        )
        started = time.monotonic()
        try:
            raw_text, params = self._invoke(prompt, model_id, spec_id)
        except Exception as error:  # noqa: BLE001 - contained by design
            generation.duration_s = time.monotonic() - started
            generation.error = f"{type(error).__name__}: {error}"
            return generation

        generation.duration_s = time.monotonic() - started
        generation.raw_text = raw_text
        generation.extracted = bool(raw_text and raw_text.strip())
        if params:
            generation.params.update(params)
        if not generation.extracted:
            generation.error = "no text returned"
        return generation

    def close(self) -> None:
        """Release resources; a no-op for CLI/HTTP providers."""
