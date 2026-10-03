"""Tests for the Claude Code CLI provider.

The interesting surface here is not the happy path but the containment rules: a
CLI agent that took extra turns or attempted a tool call did not produce a
measurement, and must be rejected rather than scored.
"""

from __future__ import annotations

import json
import os

import pytest

from codegen_evals import config, providers
from codegen_evals.providers import base, claude_code


def _payload(**overrides):
    payload = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "num_turns": 1,
        "permission_denials": [],
        "result": "```python\nx = 1\n```",
        "modelUsage": {"claude-sonnet-5-5": {"costUSD": 0.03}},
        "total_cost_usd": 0.03,
    }
    payload.update(overrides)
    return payload


# --- binary discovery --------------------------------------------------------


def test_find_claude_finds_a_native_install(monkeypatch):
    # A native install lives outside PATH, which is why `which claude` can fail.
    monkeypatch.setattr(claude_code.shutil, "which", lambda name: None)
    monkeypatch.setenv("HOME", "/Users/definitely-not-real")
    assert claude_code.find_claude() is None


def test_missing_binary_is_a_config_error(monkeypatch):
    monkeypatch.setattr(claude_code, "find_claude", lambda: None)
    with pytest.raises(base.ProviderConfigError):
        claude_code.ClaudeCodeProvider()


def test_known_install_locations_are_searched(monkeypatch, tmp_path):
    fake = tmp_path / "claude"
    fake.write_text("#!/bin/sh\n")
    monkeypatch.setattr(claude_code.shutil, "which", lambda name: None)
    monkeypatch.setattr(claude_code, "_CANDIDATE_PATHS", (str(fake),))
    assert claude_code.find_claude() == str(fake)


# --- command shape -----------------------------------------------------------


def test_command_is_headless_json_with_tools_denied():
    provider = claude_code.ClaudeCodeProvider(executable="/usr/bin/true")
    command = provider.build_command("hello", "sonnet")
    assert command[0] == "/usr/bin/true"
    assert "-p" in command
    assert "hello" in command
    assert "--output-format" in command and "json" in command
    assert "--model" in command and "sonnet" in command
    assert "--strict-mcp-config" in command
    assert "--disallowedTools" in command
    for tool in ("Bash", "Write", "Edit", "Read", "Task"):
        assert tool in command


def test_non_strict_mode_omits_tool_denials():
    provider = claude_code.ClaudeCodeProvider(executable="/usr/bin/true", strict=False)
    assert "--disallowedTools" not in provider.build_command("hi", "sonnet")


# --- output parsing ----------------------------------------------------------


def test_parse_result_reads_single_json_object():
    payload = claude_code.parse_result(json.dumps(_payload()))
    assert payload["result"] == "```python\nx = 1\n```"


def test_parse_result_rejects_empty_output():
    with pytest.raises(base.ProviderConfigError):
        claude_code.parse_result("")


def test_parse_result_rejects_non_json():
    with pytest.raises(base.ProviderConfigError):
        claude_code.parse_result("no json at all")


def test_parse_result_recovers_last_json_line_from_a_stream():
    stream = "\n".join(
        [
            json.dumps({"type": "system", "subtype": "init"}),
            json.dumps(_payload()),
        ]
    )
    assert claude_code.parse_result(stream)["result"].startswith("```python")


# --- containment: the important part -----------------------------------------


def test_error_payload_is_rejected():
    with pytest.raises(base.ProviderConfigError) as caught:
        claude_code.validate_result(
            _payload(is_error=True, result="Failed to authenticate"), "sonnet"
        )
    assert "Failed to authenticate" in str(caught.value)


def test_permission_denials_are_rejected():
    with pytest.raises(base.ProviderConfigError) as caught:
        claude_code.validate_result(
            _payload(permission_denials=[{"tool": "Bash"}]), "sonnet"
        )
    assert "tool call" in str(caught.value)


def test_multi_turn_run_is_rejected():
    with pytest.raises(base.ProviderConfigError) as caught:
        claude_code.validate_result(_payload(num_turns=4), "sonnet")
    assert "4 turns" in str(caught.value)


def test_single_turn_clean_run_is_accepted():
    claude_code.validate_result(_payload(), "sonnet")


def test_writing_into_the_scratch_dir_is_rejected(monkeypatch, tmp_path):
    """The agent must not be able to alter its working directory."""
    import subprocess

    provider = claude_code.ClaudeCodeProvider(executable="/bin/sh")
    monkeypatch.setattr(
        claude_code.tempfile, "mkdtemp", lambda prefix="": str(tmp_path)
    )

    def fake_run(command, cwd=None, capture_output=None, text=None, timeout=None):
        # Simulate an agent that wrote a file despite the denials.
        (tmp_path / "sneaky.py").write_text("print('hi')\n")
        return subprocess.CompletedProcess(
            command, 0, stdout=json.dumps(_payload()), stderr=""
        )

    monkeypatch.setattr(claude_code.subprocess, "run", fake_run)
    generation = provider.generate("prompt", "sonnet", spec_id="s")
    assert generation.extracted is False
    assert generation.error is not None
    assert "scratch dir" in generation.error


def test_timeout_is_a_config_error(monkeypatch, tmp_path):
    import subprocess

    provider = claude_code.ClaudeCodeProvider(executable="/bin/sh", timeout_s=1)
    monkeypatch.setattr(claude_code.tempfile, "mkdtemp", lambda prefix="": str(tmp_path))

    def fake_run(command, cwd=None, capture_output=None, text=None, timeout=None):
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(claude_code.subprocess, "run", fake_run)
    generation = provider.generate("prompt", "sonnet", spec_id="s")
    assert generation.extracted is False
    assert generation.error is not None
    assert "timed out" in generation.error


def test_generate_contains_provider_errors(monkeypatch, tmp_path):
    """A containment violation becomes a Generation error, not an exception."""
    import subprocess

    provider = claude_code.ClaudeCodeProvider(executable="/bin/sh")
    monkeypatch.setattr(claude_code.tempfile, "mkdtemp", lambda prefix="": str(tmp_path))

    def fake_run(command, cwd=None, capture_output=None, text=None, timeout=None):
        return subprocess.CompletedProcess(
            command, 0, stdout=json.dumps(_payload(is_error=True, result="boom")), stderr=""
        )

    monkeypatch.setattr(claude_code.subprocess, "run", fake_run)
    generation = provider.generate("prompt", "sonnet", spec_id="s")
    assert generation.extracted is False
    assert generation.error is not None
    assert "boom" in generation.error


# --- config and registry -----------------------------------------------------


def test_claude_code_is_in_the_provider_registry():
    assert "claude-code" in providers.PROVIDER_NAMES


def test_default_claude_code_model_is_an_alias():
    assert providers.default_models("claude-code") == [config.DEFAULT_CLAUDE_CODE_MODEL]


def test_judge_model_must_differ_from_subject():
    """A CLI agent must not grade its own output."""
    from codegen_evals.scoring import semantic

    provider = claude_code.ClaudeCodeProvider(executable="/usr/bin/true")
    judge = semantic.ProviderJudge(provider, "sonnet")
    verdict = judge.judge(
        semantic_spec(), "prompt", "x = 1\n", "sonnet"
    )
    assert verdict.score is None
    assert "self-grade" in verdict.error


def semantic_spec():
    from codegen_evals.models import Spec

    return Spec(
        id="fizzbuzz",
        tier="easy",
        tags=["algorithms"],
        prompt="Write fizzbuzz.",
        required_symbols=["fizzbuzz"],
    )


# --- live check (opt-in) -----------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("CODEGEN_EVALS_LIVE") != "1",
    reason="set CODEGEN_EVALS_LIVE=1 to run a live Claude Code call",
)
def test_live_claude_code_call_is_contained_and_extractable():
    provider = claude_code.ClaudeCodeProvider(timeout_s=240)
    generation = provider.generate(
        "Output ONLY a fenced python code block. Define subtract(a, b) returning a - b.",
        "sonnet",
        spec_id="smoke",
    )
    assert generation.error is None, generation.error
    assert generation.extracted is True
    assert generation.params["num_turns"] == 1
    assert "def " in (generation.code or "")
