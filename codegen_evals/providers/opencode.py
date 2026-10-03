"""Provider backed by locally installed OpenCode models.

Generation is pinned to a tools-disabled agent so the model produces a bare code
block instead of acting on the repository. See ``docs/providers.md``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .. import config
from .base import Provider, ProviderConfigError


def find_opencode() -> Optional[str]:
    """Locate the ``opencode`` executable."""
    found = shutil.which("opencode")
    if found:
        return found
    candidate = Path.home() / ".opencode" / "bin" / "opencode"
    if candidate.exists():
        return str(candidate)
    for prefix in ("/opt/homebrew/bin", "/usr/local/bin"):
        candidate = Path(prefix) / "opencode"
        if candidate.exists():
            return str(candidate)
    return None


def parse_ndjson(payload: str) -> Tuple[str, List[str]]:
    """Collect assistant text and error messages from OpenCode NDJSON output."""
    texts: List[str] = []
    errors: List[str] = []
    for line in payload.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        if kind == "text":
            part = event.get("part") or {}
            if isinstance(part.get("text"), str):
                texts.append(part["text"])
        elif kind == "error":
            errors.append(json.dumps(event.get("error") or event)[:300])
    return "".join(texts), errors


class OpenCodeProvider(Provider):
    name = "opencode"

    def __init__(
        self,
        agent: str = config.DEFAULT_AGENT,
        temperature: float = config.DEFAULT_TEMPERATURE,
        timeout_s: float = config.DEFAULT_TIMEOUT_S,
        executable: Optional[str] = None,
        directory: Optional[str] = None,
    ):
        super().__init__(temperature=temperature, timeout_s=timeout_s)
        self.executable = executable or find_opencode()
        if not self.executable:
            raise ProviderConfigError(
                "the 'opencode' executable was not found on PATH; install OpenCode "
                "or use --provider mock"
            )
        self.agent = agent
        self.directory = directory

    def build_command(self, prompt: str, model_id: str) -> List[str]:
        command = [
            self.executable,
            "run",
            "--agent",
            self.agent,
            "--model",
            model_id,
            "--format",
            "json",
        ]
        if self.directory:
            command.append(self.directory)
        command.append(prompt)
        return command

    def _invoke(
        self, prompt: str, model_id: str, spec_id: str = ""
    ) -> Tuple[str, Dict[str, Any]]:
        command = self.build_command(prompt, model_id)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except subprocess.TimeoutExpired as error:
            raise ProviderConfigError(
                f"opencode timed out after {self.timeout_s:g}s for {model_id}"
            ) from error

        if completed.returncode != 0:
            raise ProviderConfigError(
                f"opencode exited {completed.returncode} for {model_id}: "
                f"{(completed.stderr or '').strip()[:300]}"
            )

        text, errors = parse_ndjson(completed.stdout or "")
        if errors and not text:
            raise ProviderConfigError(f"opencode reported an error for {model_id}: {errors[0]}")
        return text, {"agent": self.agent, "model": model_id}

    def available_models(self) -> List[str]:
        """Ask OpenCode which models exist (best effort)."""
        executable = self.executable or find_opencode()
        if not executable:
            return []
        try:
            completed = subprocess.run(
                [executable, "models"], capture_output=True, text=True, timeout=60
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        return [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]


def opencode_environment_hint() -> str:
    """Diagnostic string used when OpenCode is missing."""
    return f"PATH={os.environ.get('PATH', '')}"
