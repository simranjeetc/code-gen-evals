"""Repeat stability, the variance guard, the control model, and the logging
contract for repeated attempts.

These tests exist because a single sample was being reported as a finding. A
gap between two models is only readable if it clears the noise, and the noise is
the repeat spread — which this change measures for the first time. Every test
here asserts that absence of a measurement is never rendered as a measurement of
zero stability.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codegen_evals import cli, config, corpus, pipeline, reporting
from codegen_evals.models import (
    OUTCOME_PROVIDER_ERROR,
    OUTCOME_SCORED,
    OUTCOME_TIMEOUT,
    DimensionScores,
    EvalResult,
    RunMetadata,
    RunResults,
)
from codegen_evals.scoring import aggregate

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_ROOT = REPO_ROOT / "corpus"


# --- helpers -----------------------------------------------------------------


def _result(
    model_id: str,
    spec_id: str,
    composite: float | None,
    repeat: int = 0,
    tier: str = "easy",
    outcome: str = OUTCOME_SCORED,
):
    scores = DimensionScores(
        execution=composite if composite is not None else 0.0,
        edge=composite if composite is not None else 0.0,
        style=composite if composite is not None else 0.0,
        semantic=composite,
    )
    return EvalResult(
        model_id=model_id,
        provider="mock",
        spec_id=spec_id,
        tier=tier,
        scores=scores,
        outcome=outcome,
        repeat=repeat,
    )


def _run(results, **meta_kwargs) -> RunResults:
    aggregate.aggregate(results, config.DEFAULT_WEIGHTS)
    metadata = RunMetadata(
        provider="mock",
        models=list({r.model_id for r in results}),
        weights=dict(config.DEFAULT_WEIGHTS),
        thresholds=dict(config.DEFAULT_THRESHOLDS),
        mock=True,
        **meta_kwargs,
    )
    return RunResults(metadata=metadata, results=results)


# --- 1.1 repeat index round-trips and the schema was bumped ------------------


def test_repeat_round_trips_through_json():
    result = EvalResult(model_id="m", spec_id="s", repeat=2)
    payload = result.to_dict()
    assert payload["repeat"] == 2
    assert EvalResult.from_dict(payload).repeat == 2


def test_old_results_default_to_repeat_zero():
    # A schema-3 file has no repeat; loading it must not invent a repeat index.
    assert EvalResult.from_dict({"model_id": "m", "spec_id": "s"}).repeat == 0


def test_schema_version_was_bumped_for_repetition():
    from codegen_evals.models import SCHEMA_VERSION

    assert SCHEMA_VERSION == 4


# --- 1.2 the loop produces k distinct attempts with distinct indices ---------


def test_repeat_count_produces_distinct_attempts():
    specs = corpus.load_corpus(CORPUS_ROOT, ids=["fizzbuzz", "json_diff"])
    run = pipeline.run_evaluation(
        specs=specs, models=["mock-strong"], provider_name="mock", repeat_count=3
    )
    pairs = {}
    for result in run.results:
        pairs.setdefault((result.spec_id, result.model_id), []).append(result.repeat)
    assert all(sorted(indices) == [0, 1, 2] for indices in pairs.values())
    assert run.metadata.repeat_count == 3


def test_default_is_one_repeat():
    specs = corpus.load_corpus(CORPUS_ROOT, ids=["fizzbuzz"])
    run = pipeline.run_evaluation(specs=specs, models=["mock-strong"], provider_name="mock")
    assert run.metadata.repeat_count == 1
    assert [r.repeat for r in run.results] == [0]


# --- 2.1 / 2.3 statistics are over scored repeats, and absence is not zero ---


def test_spread_matches_a_hand_computation():
    s = aggregate.spread([0.90, 0.94, 0.98])
    assert s["mean"] == pytest.approx(0.94)
    assert s["sd"] == pytest.approx(((0.04 ** 2) * 2 / 3) ** 0.5)
    assert s["min"] == 0.90 and s["max"] == 0.98
    assert s["measured"] is True


def test_single_repeat_is_not_measured_not_zero():
    s = aggregate.spread([0.93])
    assert s["measured"] is False
    assert s["sd"] is None
    assert s["range"] is None


def test_empty_spread_is_not_measured():
    s = aggregate.spread([])
    assert s["measured"] is False and s["sd"] is None


def test_model_stability_is_computed_within_specs_not_across_them():
    # Two specs with very different composites, each perfectly repeatable.
    # A model that is deterministic must report sd=0 even though its specs differ.
    results = [
        _result("m", "easy_spec", 0.10),
        _result("m", "easy_spec", 0.10, repeat=1),
        _result("m", "hard_spec", 0.90),
        _result("m", "hard_spec", 0.90, repeat=1),
    ]
    summary = aggregate.aggregate(results, config.DEFAULT_WEIGHTS)["by_model"]["m"]
    assert summary["stability"]["sd"] == pytest.approx(0.0)
    assert summary["stability"]["spec_sd"] == pytest.approx(0.0)
    assert summary["stability"]["measured"] is True


def test_model_stability_averages_across_specs():
    # Spec A ranges 0.00..0.00 (sd 0), spec B ranges 0.80..1.00 (sd 0.10).
    # Mean per-spec sd = 0.05; widest spec sd = 0.10.
    results = [
        _result("m", "a", 1.00),
        _result("m", "a", 1.00, repeat=1),
        _result("m", "b", 0.80),
        _result("m", "b", 1.00, repeat=1),
    ]
    summary = aggregate.aggregate(results, config.DEFAULT_WEIGHTS)["by_model"]["m"]
    assert summary["stability"]["sd"] == pytest.approx(0.05)
    assert summary["stability"]["spec_sd"] == pytest.approx(0.10)


def test_unstable_spec_is_visible_per_spec():
    results = [
        _result("m", "wild", 0.40),
        _result("m", "wild", 0.95, repeat=1),
    ]
    summary = aggregate.aggregate(results, config.DEFAULT_WEIGHTS)
    row = summary["by_spec_model"]["wild"]["m"]
    assert row["sd"] > 0.20
    assert row["range"] == pytest.approx(0.55)


def test_statistics_exclude_infrastructure_failures():
    results = [
        _result("m", "s", 0.90),
        _result("m", "s", None, repeat=1, outcome=OUTCOME_TIMEOUT),
        _result("m", "s", 0.94, repeat=2),
    ]
    summary = aggregate.aggregate(results, config.DEFAULT_WEIGHTS)["by_model"]["m"]
    # The timeout must not enter the spread; only 0.90 and 0.94 do.
    assert summary["stability"]["mean"] == pytest.approx(0.92)
    assert summary["stability"]["sd"] == pytest.approx(0.02)
    assert summary["excluded"] == 1


# --- 2.4 dimension spreads are reported -------------------------------------


def test_dimension_spreads_are_recorded():
    results = [
        _result("m", "s", 0.50),
        _result("m", "s", 1.00, repeat=1),
    ]
    summary = aggregate.aggregate(results, config.DEFAULT_WEIGHTS)["by_model"]["m"]
    spreads = summary["dimension_spread"]
    assert set(spreads) == set(("execution", "edge", "semantic", "style"))
    assert spreads["execution"]["sd"] == pytest.approx(0.25)


# --- 3.1 / 3.2 variance guard -----------------------------------------------


def test_variance_guard_fires_above_threshold():
    results = [
        _result("steady", "s", 0.90),
        _result("steady", "s", 0.90, repeat=1),
        _result("wobbly", "s", 0.50),
        _result("wobbly", "s", 1.00, repeat=1),
    ]
    reason, models = aggregate.variance_reason(
        results, 0.05, weights=config.DEFAULT_WEIGHTS
    )
    assert models == ["wobbly"]
    assert "wobbly" in reason
    assert "0.050" in reason
    # The interpretation rule is stated, not implied.
    assert "2x sd" in reason or "2.0x sd" in reason


def test_variance_guard_does_not_fire_below_threshold():
    results = [
        _result("m", "s", 0.90),
        _result("m", "s", 0.93, repeat=1),
    ]
    reason, models = aggregate.variance_reason(
        results, 0.05, weights=config.DEFAULT_WEIGHTS
    )
    assert reason is None and models == []


def test_variance_guard_is_silent_when_spread_is_unmeasured():
    # One repeat each: no spread to guard on, so no model is flagged.
    results = [_result("m", "s", 0.90), _result("other", "s", 0.50)]
    reason, models = aggregate.variance_reason(
        results, 0.05, weights=config.DEFAULT_WEIGHTS
    )
    assert reason is None and models == []


# --- 3.3 guards are independent ---------------------------------------------


def _run_with_metadata(results, **kwargs) -> RunResults:
    return _run(results, **kwargs)


def test_variance_guard_is_independent_of_the_other_two():
    # Unstable but neither degenerate (models differ) nor unreliable (no failures).
    results = [
        _result("a", "s", 0.50),
        _result("a", "s", 1.00, repeat=1),
        _result("b", "s", 0.20),
        _result("b", "s", 0.30, repeat=1),
    ]
    var_reason, var_models = aggregate.variance_reason(
        results, 0.05, weights=config.DEFAULT_WEIGHTS
    )
    assert var_reason is not None and var_models
    assert aggregate.degenerate_reason(results) is None
    assert aggregate.unreliable_reason(results, 0.2) == (None, [])


def test_unreliable_does_not_imply_unstable():
    results = [
        _result("a", "s", 0.90),
        _result("a", "s", None, repeat=1, outcome=OUTCOME_PROVIDER_ERROR),
        _result("a", "s", None, repeat=2, outcome=OUTCOME_PROVIDER_ERROR),
        _result("b", "s", 0.80),
        _result("b", "s", 0.80, repeat=1),
    ]
    unreliable_reason, flagged = aggregate.unreliable_reason(results, 0.2)
    assert unreliable_reason is not None and flagged == ["a"]
    # 'a' has only one scored attempt, so no spread; nothing is unstable.
    var_reason, _ = aggregate.variance_reason(
        results, 0.05, weights=config.DEFAULT_WEIGHTS
    )
    assert var_reason is None


def test_unstable_run_still_persists_and_exits_non_zero(tmp_path, monkeypatch, capsys):
    specs = corpus.load_corpus(CORPUS_ROOT, ids=["fizzbuzz"])
    run = pipeline.run_evaluation(specs=specs, models=["mock-strong"], provider_name="mock")
    run.metadata.unstable = True
    run.metadata.unstable_models = ["mock-strong"]
    run.metadata.unstable_reason = "sd exceeds threshold"
    monkeypatch.setattr(pipeline, "run_evaluation", lambda **kwargs: run)

    out = tmp_path / "results.json"
    exit_code = cli.main(
        ["run", "--provider", "mock", "--specs", "fizzbuzz", "--out", str(out), "--quiet"]
    )
    assert exit_code == cli.EXIT_PROBLEM
    payload = json.loads(out.read_text())
    assert payload["schema_version"] == 4
    assert payload["metadata"]["unstable"] is True
    assert "UNSTABLE" in capsys.readouterr().err


def test_variance_guard_rule_is_recorded_with_the_run():
    specs = corpus.load_corpus(CORPUS_ROOT, ids=["fizzbuzz"])
    run = pipeline.run_evaluation(
        specs=specs, models=["mock-strong"], provider_name="mock", repeat_count=2
    )
    assert run.metadata.variance_threshold == config.VARIANCE_THRESHOLD
    assert run.metadata.instability_multiplier == config.INSTABILITY_MULTIPLIER


# --- 4. logging --------------------------------------------------------------


def test_default_run_emits_one_summary_line_per_model(capsys, tmp_path):
    specs = corpus.load_corpus(CORPUS_ROOT, ids=["fizzbuzz", "json_diff"])
    exit_code = cli.main(
        [
            "run", "--provider", "mock", "--specs", "fizzbuzz,json_diff",
            "--models", "mock-strong,mock-weak", "--out",
            str(tmp_path / "rs_test.json"),
        ]
    )
    err = capsys.readouterr().err
    assert exit_code == cli.EXIT_OK
    # One line per model, and no per-attempt lines.
    assert err.count("mean=") >= 2
    assert "repeat 1/" not in err


def test_verbose_run_shows_each_attempt(capsys, tmp_path):
    out = tmp_path / "rs_test2.json"
    cli.main(
        [
            "run", "--provider", "mock", "--specs", "fizzbuzz",
            "--models", "mock-strong", "--repeats", "2", "-v", "--out", str(out),
        ]
    )
    err = capsys.readouterr().err
    assert "repeat 1/2" in err
    assert "repeat 2/2" in err


def test_guard_reason_is_a_single_readable_line(capsys, tmp_path):
    specs = corpus.load_corpus(CORPUS_ROOT, ids=["fizzbuzz"])
    run = pipeline.run_evaluation(specs=specs, models=["mock-strong"], provider_name="mock")
    run.metadata.unstable = True
    run.metadata.unstable_models = ["mock-strong"]
    run.metadata.unstable_reason = (
        "composite standard deviation exceeds the 0.050 threshold for "
        "`mock-strong` (sd=0.071)"
    )
    import codegen_evals.pipeline as pipeline_module

    original = pipeline_module.run_evaluation

    def fake(**kwargs):
        return run

    pipeline_module.run_evaluation = fake
    try:
        cli.main(
            [
                "run", "--provider", "mock", "--specs", "fizzbuzz", "--out",
                str(tmp_path / "rs_test3.json"),
            ]
        )
    finally:
        pipeline_module.run_evaluation = original
    err = capsys.readouterr().err
    assert err.count("UNSTABLE:") == 1
    assert "0.071" in err


# --- 5. control model --------------------------------------------------------


def test_control_separated_when_it_scores_below_the_subjects():
    results = [
        _result("strong_a", "s", 0.95),
        _result("strong_a", "s", 0.95, repeat=1),
        _result("strong_b", "s", 0.92),
        _result("strong_b", "s", 0.92, repeat=1),
        _result("control", "s", 0.40),
        _result("control", "s", 0.40, repeat=1),
    ]
    summary = aggregate.aggregate(results, config.DEFAULT_WEIGHTS)
    separated, reason = aggregate.control_reason(summary["by_model"], "control")
    assert separated is True
    assert "discriminates" in reason


def test_control_not_separated_when_it_scores_with_the_subjects():
    results = [
        _result("strong_a", "s", 0.95),
        _result("strong_a", "s", 0.95, repeat=1),
        _result("strong_b", "s", 0.92),
        _result("strong_b", "s", 0.92, repeat=1),
        _result("control", "s", 0.91),
        _result("control", "s", 0.91, repeat=1),
    ]
    summary = aggregate.aggregate(results, config.DEFAULT_WEIGHTS)
    separated, reason = aggregate.control_reason(summary["by_model"], "control")
    assert separated is False
    assert "cannot discriminate" in reason


def test_absent_control_is_stated_not_silent():
    separated, reason = aggregate.control_reason({}, None)
    assert separated is None
    assert "not measured" in reason


def test_control_with_no_scored_attempts_is_reported_unmeasured():
    results = [
        _result("strong", "s", 0.90),
        _result("control", "s", None, outcome=OUTCOME_PROVIDER_ERROR),
    ]
    summary = aggregate.aggregate(results, config.DEFAULT_WEIGHTS)
    separated, reason = aggregate.control_reason(summary["by_model"], "control")
    assert separated is None
    assert "not measured" in reason


def test_control_is_never_presented_as_a_ranked_peer():
    run = _run(
        [
            _result("strong", "s", 0.90),
            _result("control", "s", 0.40),
        ],
        control_model="control",
        control_separated=True,
        control_reason="the corpus separated the control",
    )
    report = reporting.render_report(run)
    assert "_(control)_" in report
    assert "not a ranked peer" in report


def test_control_section_states_the_reading():
    run = _run(
        [
            _result("strong", "s", 0.90),
            _result("control", "s", 0.40),
        ],
        control_model="control",
        control_separated=False,
        control_reason="the corpus did not separate the control",
    )
    report = reporting.render_report(run)
    assert "## Control model" in report
    assert "harder specs are the fix" in report


# --- 6. naming honesty -------------------------------------------------------


def test_no_pass_at_k_wording_anywhere():
    specs = corpus.load_corpus(CORPUS_ROOT, ids=["fizzbuzz", "json_diff"])
    run = pipeline.run_evaluation(
        specs=specs, models=["mock-strong"], provider_name="mock", repeat_count=2,
        control_model=None,
    )
    report = reporting.render_report(run)
    # The report explicitly rejects the term; it must not use it as a label.
    assert "pass@k" not in report.replace("not `pass@k`", "").replace("it is not `pass@k`", "")
    payload = json.dumps(run.to_dict())
    assert "pass@k" not in payload


def test_report_states_what_stability_measures():
    specs = corpus.load_corpus(CORPUS_ROOT, ids=["fizzbuzz"])
    run = pipeline.run_evaluation(
        specs=specs, models=["mock-strong"], provider_name="mock", repeat_count=2
    )
    report = reporting.render_report(run)
    assert "repeatability, not eventual success" in report
