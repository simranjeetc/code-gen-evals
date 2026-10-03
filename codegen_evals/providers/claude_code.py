"""Provider backed by the Claude Code CLI.

Claude Code is a subscription product whose CLI is the only way to reach the
model — there is no API path for it. ``claude -p`` is genuinely headless and does
not need a TTY, so shelling out works.

The catch, and the reason this provider is careful: Claude Code is an *agent*.
Installed in a repository it may read files, run shell commands, or edit the
working tree, which would make the measurement depend on the machine and could
change the user's files. This provider therefore runs every call from a throwaway
directory outside the repo, denies every tool, and disables MCP servers so no
capability leaks back in. Results are rejected unless the call reports a single
turn and no permission denials.

Verified shape (2026-10-03, claude 2.1.286):

    {"type": "result", "subtype": "success", "is_error": false,
     "result": "```python\\n...\\n```", "num_turns": 1,
     "permission_denials": [], "modelUsage": {"claude-sonnet-5": {...}}}

Unlike OpenCode this is a single JSON object, not NDJSON, so parsing is a plain
``json.loads`` on stdout.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import Provider, ProviderConfigError, ProviderTimeout

# Every tool that could touch the filesystem, the network, or spawn work.
DENIED_TOOLS = (
    "Bash",
    "Edit",
    "Write",
    "Read",
    "Glob",
    "Grep",
    "WebFetch",
    "WebSearch",
    "Task",
    "NotebookEdit",
)

DEFAULT_MODEL = "sonnet"

# Where a native install puts the binary. `~/.local/bin` is frequently absent from
# PATH, which is why `which claude` can fail on a working install.
_CANDIDATE_PATHS = (
    "~/.local/bin/claude",
    "~/.claude/local/claude",
    "/opt/homebrew/bin/claude",
    "/usr/local/bin/claude",
)


def find_claude() -> Optional[str]:
    """Locate the ``claude`` executable, PATH first then known install dirs."""
    found = shutil.which("claude")
    if found:
        return found
    for candidate in _CANDIDATE_PATHS:
        path = Path(os.path.expanduser(candidate))
        if path.exists():
            return str(path)
    return None


def parse_result(stdout: str) -> Dict[str, Any]:
    """Parse the single JSON object ``claude -p --output-format json`` prints."""
    text = (stdout or "").strip()
    if not text:
        raise ProviderConfigError("claude returned no output")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Older builds can emit a stream; take the last JSON object on a line.
        for line in reversed(text.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        raise ProviderConfigError(f"claude output was not JSON: {text[:200]}") from None


def validate_result(payload: Dict[str, Any], model_id: str) -> None:
    """Reject a run that was not a bare, tool-free completion.

    A provider is not trustworthy just because it returned text. If the agent took
    more than one turn or tried to use a tool, the number it produced is not a
    measurement of code generation.
    """
    if payload.get("is_error"):
        raise ProviderConfigError(
            f"claude reported an error for {model_id}: {str(payload.get('result'))[:200]}"
        )
    denials = payload.get("permission_denials") or []
    if denials:
        raise ProviderConfigError(
            f"claude attempted {len(denials)} tool call(s) for {model_id} despite "
            "denials; refusing to score a non-bare completion"
        )
    turns = payload.get("num_turns")
    if isinstance(turns, int) and turns > 1:
        raise ProviderConfigError(
            f"claude took {turns} turns for {model_id}; expected a single-turn completion"
        )


class ClaudeCodeProvider(Provider):
    """Subject provider: bare code generation through the Claude Code CLI."""

    name = "claude-code"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.0,
        timeout_s: float = 240.0,
        executable: Optional[str] = None,
        strict: bool = True,
    ):
        super().__init__(temperature=temperature, timeout_s=timeout_s)
        self.executable = executable or find_claude()
        if not self.executable:
            raise ProviderConfigError(
                "the 'claude' executable was not found; looked on PATH and in "
                "~/.local/bin, ~/.claude/local, /opt/homebrew/bin, /usr/local/bin"
            )
        self.model = model
        self.strict = strict

    def build_command(self, prompt: str, model_id: str) -> List[str]:
        command = [
            self.executable,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--model",
            model_id or self.model,
            "--strict-mcp-config",
        ]
        if self.strict:
            command += ["--disallowedTools", *DENIED_TOOLS]
        return command

    def _invoke(
        self, prompt: str, model_id: str, spec_id: str = "", timeout_s: Optional[float] = None
    ) -> Tuple[str, Dict[str, Any]]:
        command = self.build_command(prompt, model_id)
        budget = timeout_s or self.timeout_s
        # Run outside the repository so the agent cannot see or alter the corpus,
        # and so two runs on two machines are comparable.
        workdir = tempfile.mkdtemp(prefix="codegen-eval-claude-")
        try:
            try:
                completed = subprocess.run(
                    command,
                    cwd=workdir,
                    capture_output=True,
                    text=True,
                    timeout=budget,
                )
            except subprocess.TimeoutExpired as error:
                raise ProviderTimeout(
                    f"claude timed out after {budget:g}s for {model_id}"
                ) from error

            if completed.returncode != 0 and not (completed.stdout or "").strip():
                raise ProviderConfigError(
                    f"claude exited {completed.returncode} for {model_id}: "
                    f"{(completed.stderr or '').strip()[:300]}"
                )

            payload = parse_result(completed.stdout or "")
            validate_result(payload, model_id)
            leftover = list(Path(workdir).iterdir())
            if leftover:
                raise ProviderConfigError(
                    f"claude wrote {len(leftover)} file(s) into the scratch dir; "
                    "refusing to score a run that modified its working directory"
                )
            return payload.get("result", "") or "", {
                "model": model_id,
                "resolved_model": next(iter((payload.get("modelUsage") or {}).keys()), None),
                "num_turns": payload.get("num_turns"),
                "cost_usd": payload.get("total_cost_usd"),
            }
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


class ClaudeCodeJudgeProvider(ClaudeCodeProvider):
    """Judge provider: same containment, but returns raw text for JSON parsing.

    Uses ``generate_text`` so a judge reply containing a fenced block is not
    reinterpreted as a candidate solution.
    """

    name = "claude-code-judge"
