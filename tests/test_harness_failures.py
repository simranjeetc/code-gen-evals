"""Outcome classification, exclusion, retries, the exclusion-rate guard, and
the report sections that surface them.

These tests exist because a harness failure scored as ``0.0`` once produced a
false finding. Every test here asserts that a failure and a weak model are
rendered differently.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from codegen_evals import cli, config, corpus, pipeline, reporting
from codegen_evals.models import (
    OUTCOME_PROVIDER_ERROR,
    OUTCOME_SCORED,
    OUTCOME_TIMEOUT,
    OUTCOME_UNPARSEABLE_OUTPUT,
    DimensionScores,
    EvalResult,
    Generation,
    RunMetadata,
    RunResults,
)
from codegen_evals.providers import base, claude_code, opencode
from codegen_evals.scoring import aggregate

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_ROOT = REPO_ROOT / "corpus"


# --- helpers -----------------------------------------------------------------


class _StaticProvider(base.Provider):
    """A provider that returns one fixed body, through the real extraction path."""

    name = "static"

    def __init__(self, body: str):
        super().__init__()
        self._body = body

    def _invoke(self, prompt, model_id, spec_id="", timeout_s=None):
        return self._body, {}


class ScriptedProvider:
    """Returns queued :class:`Generation` objects and records every call."""

    name = "scripted"

    def __init__(self, generations):
        self._generations = list(generations)
        self.calls = []
        self.timeouts = []

    def generate(self, prompt, model_id, spec_id="", timeout_s=None):
        self.calls.append((model_id, spec_id))
        self.timeouts.append(timeout_s)
        generation = self._generations.pop(0)
        generation.model_id = model_id
        generation.provider = self.name
        generation.spec_id = spec_id
        return generation


def _scored_generation(code: str) -> Generation:
    return _StaticProvider("```python\n" + code + "```").generate("p", "m")


def _timeout_generation(message: str = "timed out after 1s") -> Generation:
    return Generation(outcome=OUTCOME_TIMEOUT, error=f"ProviderTimeout: {message}")


def _result(model_id, spec_id, tier, scores, outcome=OUTCOME_SCORED, tags=("algorithms",)):
    return EvalResult(
        model_id=model_id,
        provider="mock",
        spec_id=spec_id,
        tier=tier,
        tags=list(tags),
        scores=scores,
        outcome=outcome,
        generation_error=None if outcome == OUTCOME_SCORED else f"{outcome} for {model_id}",
    )


def _spec(spec_id: str = "fizzbuzz"):
    return corpus.load_corpus(CORPUS_ROOT, ids=[spec_id])[0]


# --- 1.1 outcome round-trips and schema bump --------------------------------


def test_outcome_and_retry_count_round_trip_through_json():
    result = EvalResult(
        model_id="m",
        provider="opencode",
        spec_id="s",
        tier="hard",
        outcome=OUTCOME_TIMEOUT,
        retry_count=1,
        generation_error="ProviderTimeout: boom",
    )
    payload = result.to_dict()
    assert payload["outcome"] == OUTCOME_TIMEOUT
    assert payload["retry_count"] == 1
    restored = EvalResult.from_dict(payload)
    assert restored.outcome == OUTCOME_TIMEOUT
    assert restored.retry_count == 1
    assert restored.generation_error == "ProviderTimeout: boom"


def test_old_results_default_to_scored():
    # A schema-1 file has no outcome; loading it must not invent a failure.
    restored = EvalResult.from_dict({"model_id": "m", "spec_id": "s"})
    assert restored.outcome == OUTCOME_SCORED
    assert restored.retry_count == 0


def test_schema_version_was_bumped():
    from codegen_evals.models import SCHEMA_VERSION

    assert SCHEMA_VERSION == 4


# --- 1.2 / 1.3 / 1.4 provider-boundary classification -----------------------


def test_opencode_timeout_is_classified(monkeypatch):
    provider = opencode.OpenCodeProvider(executable="/usr/bin/true", timeout_s=1)

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 1)

    monkeypatch.setattr(opencode.subprocess, "run", fake_run)
    generation = provider.generate("p", "opencode-go/mimo-v2.6-flash", spec_id="s")
    assert generation.outcome == OUTCOME_TIMEOUT
    assert generation.outcome != OUTCOME_SCORED
    assert "timed out" in generation.error


def test_opencode_nonzero_exit_is_classified(monkeypatch):
    provider = opencode.OpenCodeProvider(executable="/usr/bin/true")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, stdout="", stderr="boom")

    monkeypatch.setattr(opencode.subprocess, "run", fake_run)
    generation = provider.generate("p", "m", spec_id="s")
    assert generation.outcome == OUTCOME_PROVIDER_ERROR


def test_claude_timeout_is_classified(monkeypatch, tmp_path):
    provider = claude_code.ClaudeCodeProvider(executable="/bin/sh", timeout_s=1)
    monkeypatch.setattr(claude_code.tempfile, "mkdtemp", lambda prefix="": str(tmp_path))

    def fake_run(command, cwd=None, capture_output=None, text=None, timeout=None):
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(claude_code.subprocess, "run", fake_run)
    generation = provider.generate("p", "sonnet", spec_id="s")
    assert generation.outcome == OUTCOME_TIMEOUT


def test_claude_is_error_is_classified(monkeypatch, tmp_path):
    provider = claude_code.ClaudeCodeProvider(executable="/bin/sh")
    monkeypatch.setattr(claude_code.tempfile, "mkdtemp", lambda prefix="": str(tmp_path))
    payload = {
        "type": "result",
        "is_error": True,
        "result": "Failed to authenticate",
        "num_turns": 1,
        "permission_denials": [],
    }

    def fake_run(command, cwd=None, capture_output=None, text=None, timeout=None):
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(claude_code.subprocess, "run", fake_run)
    generation = provider.generate("p", "sonnet", spec_id="s")
    assert generation.outcome == OUTCOME_PROVIDER_ERROR


def test_unparseable_output_is_not_a_provider_error():
    generation = _StaticProvider("I will not give you code.").generate("p", "m")
    assert generation.outcome == OUTCOME_UNPARSEABLE_OUTPUT
    assert generation.outcome not in (OUTCOME_TIMEOUT, OUTCOME_PROVIDER_ERROR)


# --- 1.5 a sandbox crash stays scored ---------------------------------------


def test_sandbox_crash_is_scored_not_infrastructure():
    spec = _spec("fizzbuzz")
    crashed = "def fizzbuzz(n):\n    raise RuntimeError('boom')\n"
    provider = ScriptedProvider([_scored_generation(crashed)])
    result = pipeline.evaluate_pair(
        spec=spec,
        model_id="m",
        provider=provider,
        judge=None,
        weights={"execution": 1.0},
        thresholds=dict(config.DEFAULT_THRESHOLDS),
        suite_timeout_s=30.0,
    )
    assert result.outcome == OUTCOME_SCORED
    assert result.scores.execution == 0.0


def test_runner_start_failure_is_infrastructure(monkeypatch):
    spec = _spec("fizzbuzz")
    provider = ScriptedProvider([_scored_generation("x = 1\n")])

    def boom(*args, **kwargs):
        raise OSError("python not found")

    monkeypatch.setattr(pipeline.execution, "run_spec", boom)
    result = pipeline.evaluate_pair(
        spec=spec,
        model_id="m",
        provider=provider,
        judge=None,
        weights={"execution": 1.0},
        thresholds=dict(config.DEFAULT_THRESHOLDS),
    )
    assert result.outcome == OUTCOME_PROVIDER_ERROR
    assert result.composite is None


# --- 2.1 - 2.4 exclusion-aware aggregation ----------------------------------


def test_excluded_attempt_does_not_change_an_average():
    results = [
        _result("a", "s1", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0)),
        _result("a", "s2", "easy", DimensionScores(0.0, 0.0, 0.0, 0.0), outcome=OUTCOME_TIMEOUT),
    ]
    summary = aggregate.aggregate(results, {"execution": 1.0})
    assert summary["by_model"]["a"]["execution"] == 1.0  # the excluded zero did not deflate it
    assert summary["by_model"]["a"]["n"] == 1
    assert summary["by_model"]["a"]["excluded"] == 1
    assert summary["by_tier"]["a"]["easy"]["execution"] == 1.0
    assert summary["by_tier"]["a"]["easy"]["excluded"] == 1
    assert summary["by_task_type"]["a"]["algorithms"]["execution"] == 1.0
    assert summary["by_task_type"]["a"]["algorithms"]["excluded"] == 1


def test_excluded_counts_match_raw_data():
    results = [
        _result("a", "s1", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0)),
        _result("a", "s2", "easy", DimensionScores(0.0, 0.0, 0.0, 0.0), outcome=OUTCOME_TIMEOUT),
        _result("a", "s3", "easy", DimensionScores(0.0, 0.0, 0.0, 0.0), outcome=OUTCOME_PROVIDER_ERROR),
        _result("b", "s1", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0)),
    ]
    summary = aggregate.aggregate(results, {"execution": 1.0})["by_model"]
    assert summary["a"]["excluded"] == 2
    assert summary["a"]["excluded_outcomes"] == {
        OUTCOME_TIMEOUT: 1,
        OUTCOME_PROVIDER_ERROR: 1,
    }
    assert summary["b"]["excluded"] == 0


def test_recomputation_by_hand_agrees():
    results = [
        _result("a", f"s{i}", "easy", DimensionScores(value, value, value, value))
        for i, value in enumerate((1.0, 0.5, 0.0))
    ]
    results.append(
        _result("a", "s3", "easy", DimensionScores(0.0, 0.0, 0.0, 0.0), outcome=OUTCOME_TIMEOUT)
    )
    summary = aggregate.aggregate(results, {"execution": 1.0})["by_model"]["a"]
    scored = [r for r in results if r.scored]
    hand = sum(r.scores.execution for r in scored) / len(scored)
    assert summary["execution"] == pytest.approx(hand)
    assert summary["n"] == len(scored)


def test_semantic_abstention_and_infrastructure_exclusion_are_counted_separately():
    results = [
        _result("a", "s1", "easy", DimensionScores(1.0, 1.0, 1.0, None)),  # judge abstained
        _result("a", "s2", "easy", DimensionScores(0.0, 0.0, 0.0, 0.0), outcome=OUTCOME_TIMEOUT),
    ]
    summary = aggregate.aggregate(results, {"execution": 1.0})["by_model"]["a"]
    assert summary["semantic_abstentions"] == 1
    assert summary["excluded"] == 1


def test_excluded_results_have_no_composite():
    results = [
        _result("a", "s1", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0), outcome=OUTCOME_PROVIDER_ERROR),
    ]
    aggregate.aggregate(results, config.DEFAULT_WEIGHTS)
    assert results[0].composite is None


def test_saved_results_carry_exclusion_counts_matching_raw_data(tmp_path):
    run = _run_with_failure()
    path = tmp_path / "results.json"
    reporting.save_results(run, path)
    payload = json.loads(path.read_text())
    summary = payload["summary"]["by_model"]["mock-weak"]
    assert summary["excluded"] == 1
    assert summary["excluded_outcomes"] == {OUTCOME_TIMEOUT: 1}

    raw_excluded = [
        row for row in payload["results"] if row["outcome"] != OUTCOME_SCORED
    ]
    assert len(raw_excluded) == summary["excluded"]
    assert {row["outcome"] for row in raw_excluded} == set(summary["excluded_outcomes"])


# --- 3.1 - 3.3 retry policy -------------------------------------------------


def test_timeout_retried_once_and_recorded_as_scored():
    spec = _spec("fizzbuzz")
    provider = ScriptedProvider([_timeout_generation(), _scored_generation("x = 1\n")])
    result = pipeline.evaluate_pair(
        spec=spec,
        model_id="m",
        provider=provider,
        judge=None,
        weights={"execution": 1.0},
        thresholds=dict(config.DEFAULT_THRESHOLDS),
        timeout_s=10.0,
    )
    assert len(provider.calls) == 2
    assert provider.timeouts[1] > provider.timeouts[0]  # retried with a longer budget
    assert result.outcome == OUTCOME_SCORED
    assert result.retry_count == 1


def test_retries_are_bounded_to_two_attempts():
    spec = _spec("fizzbuzz")
    provider = ScriptedProvider([_timeout_generation(), _timeout_generation()])
    result = pipeline.evaluate_pair(
        spec=spec,
        model_id="m",
        provider=provider,
        judge=None,
        weights={"execution": 1.0},
        thresholds=dict(config.DEFAULT_THRESHOLDS),
        timeout_s=10.0,
    )
    assert len(provider.calls) == 2
    assert result.outcome == OUTCOME_TIMEOUT


def test_unparseable_output_is_not_retried():
    spec = _spec("fizzbuzz")
    provider = ScriptedProvider(
        [Generation(outcome=OUTCOME_UNPARSEABLE_OUTPUT, error="no fenced code block")]
    )
    result = pipeline.evaluate_pair(
        spec=spec,
        model_id="m",
        provider=provider,
        judge=None,
        weights={"execution": 1.0},
        thresholds=dict(config.DEFAULT_THRESHOLDS),
        timeout_s=10.0,
    )
    assert len(provider.calls) == 1
    assert result.outcome == OUTCOME_UNPARSEABLE_OUTPUT


def test_default_timeout_was_raised_for_large_hard_specs():
    assert config.DEFAULT_TIMEOUT_S >= 240.0
    assert config.RETRY_TIMEOUT_MULTIPLIER > 1.0


# --- 4.1 - 4.4 exclusion-rate guard -----------------------------------------


def test_high_exclusion_rate_flags_the_run_and_names_the_model():
    results = [
        _result("a", "s1", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0)),
        _result("a", "s2", "easy", DimensionScores(0.0, 0.0, 0.0, 0.0), outcome=OUTCOME_TIMEOUT),
        _result("a", "s3", "easy", DimensionScores(0.0, 0.0, 0.0, 0.0), outcome=OUTCOME_TIMEOUT),
        _result("b", "s1", "easy", DimensionScores(0.5, 0.5, 0.5, 0.5)),
    ]
    reason, names = aggregate.unreliable_reason(results, 0.2)
    assert reason is not None
    assert names == ["a"]
    assert "a" in reason


def test_low_exclusion_rate_does_not_flag():
    results = [
        _result("a", f"s{i}", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0))
        for i in range(19)
    ]
    results.append(
        _result("a", "s20", "easy", DimensionScores(0.0, 0.0, 0.0, 0.0), outcome=OUTCOME_TIMEOUT)
    )
    reason, names = aggregate.unreliable_reason(results, 0.2)
    assert reason is None
    assert names == []


def test_guard_is_independent_of_the_degenerate_guard():
    # Unreliable but not degenerate: scores differ, one model mostly failed.
    unreliable = [
        _result("a", "s1", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0)),
        _result("a", "s2", "easy", DimensionScores(0.0, 0.0, 0.0, 0.0), outcome=OUTCOME_TIMEOUT),
        _result("a", "s3", "easy", DimensionScores(0.0, 0.0, 0.0, 0.0), outcome=OUTCOME_TIMEOUT),
        _result("b", "s1", "easy", DimensionScores(0.3, 0.4, 0.5, 0.6)),
    ]
    assert aggregate.degenerate_reason(unreliable) is None
    assert aggregate.unreliable_reason(unreliable, 0.2)[0] is not None

    # Degenerate but not unreliable: every scored attempt is identical.
    degenerate = [
        _result("a", "s1", "easy", DimensionScores(0.5, 0.5, 0.5, 0.5)),
        _result("b", "s1", "easy", DimensionScores(0.5, 0.5, 0.5, 0.5)),
    ]
    assert aggregate.degenerate_reason(degenerate) is not None
    assert aggregate.unreliable_reason(degenerate, 0.2)[0] is None


# --- 5.1 - 5.4 the report never renders a failure as a score -----------------


def _run_with_failure(unreliable=False):
    results = [
        _result("mock-strong", "fizzbuzz", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0)),
        _result(
            "mock-weak",
            "json_diff",
            "hard",
            DimensionScores(0.0, 0.0, 0.0, 0.0),
            outcome=OUTCOME_TIMEOUT,
        ),
    ]
    results[1].generation_error = "ProviderTimeout: opencode timed out after 300s"
    aggregate.aggregate(results, config.DEFAULT_WEIGHTS)
    metadata = RunMetadata(
        provider="opencode",
        models=["mock-strong", "mock-weak"],
        weights=dict(config.DEFAULT_WEIGHTS),
        thresholds=dict(config.DEFAULT_THRESHOLDS),
        mock=False,
        unreliable=unreliable,
        unreliable_models=["mock-weak"] if unreliable else [],
        unreliable_reason="too many failures" if unreliable else None,
    )
    return RunResults(metadata=metadata, results=results)


def test_reliability_section_lists_failures_with_outcome_and_message():
    report = reporting.render_report(_run_with_failure())
    assert "## Reliability" in report
    assert "`timeout`" in report
    assert "opencode timed out after 300s" in report


def test_report_shows_exclusion_counts_next_to_aggregates():
    report = reporting.render_report(_run_with_failure())
    assert "| Model | Composite | execution | edge | semantic | style | n | excl |" in report
    assert "attempts" in report  # reliability per-model denominator table


def test_per_spec_table_never_shows_a_failure_as_a_low_score():
    report = reporting.render_report(_run_with_failure())
    assert "_excluded (timeout)_" in report
    # The excluded model/spec row must not carry a numeric composite.
    assert "| json_diff | hard | `mock-weak` | 0.00" not in report


def test_unreliable_run_is_stated_prominently():
    report = reporting.render_report(_run_with_failure(unreliable=True))
    assert "UNRELIABLE RUN" in report
    assert "mock-weak" in report


def test_unreliable_run_writes_results_and_exits_non_zero(tmp_path, monkeypatch, capsys):
    fake_run = _run_with_failure(unreliable=True)
    fake_run.metadata.provider = "mock"
    monkeypatch.setattr(pipeline, "run_evaluation", lambda **kwargs: fake_run)

    results = tmp_path / "results.json"
    exit_code = cli.main(
        ["run", "--provider", "mock", "--specs", "fizzbuzz", "--out", str(results), "--quiet"]
    )
    assert exit_code == cli.EXIT_PROBLEM
    assert results.exists()
    assert json.loads(results.read_text())["schema_version"] == 4
    assert "UNRELIABLE" in capsys.readouterr().err
