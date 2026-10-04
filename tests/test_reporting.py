"""Tests for results serialization and Markdown report rendering."""

from __future__ import annotations

import json
import socket
from pathlib import Path

from codegen_evals import config, reporting
from codegen_evals.models import (
    DISAGREEMENT_FRAGILE,
    Disagreement,
    DimensionScores,
    EvalResult,
    ExecutionEvidence,
    RunMetadata,
    RunResults,
)
from codegen_evals.scoring import aggregate, disagreements


def _result(model_id, spec_id, tier, tags, scores, disagreements_list=()):
    return EvalResult(
        model_id=model_id,
        provider="mock",
        spec_id=spec_id,
        tier=tier,
        tags=list(tags),
        scores=scores,
        ground_truth=ExecutionEvidence(suite="ground_truth", total=4, passed=["a"] * int(scores.execution * 4)),
        edge_case=ExecutionEvidence(suite="edge_case", total=4, passed=["b"] * int(scores.edge * 4)),
        extraction_ok=True,
        disagreements=list(disagreements_list),
    )


def _run(inconclusive=False, with_disagreements=True):
    results = [
        _result("mock-strong", "fizzbuzz", "easy", ["algorithms"], DimensionScores(1.0, 1.0, 1.0, 1.0)),
        _result("mock-strong", "json_diff", "hard", ["recursion"], DimensionScores(0.75, 0.5, 1.0, 0.5)),
        _result("mock-weak", "fizzbuzz", "easy", ["algorithms"], DimensionScores(0.5, 0.0, 0.6, 0.5)),
        _result("mock-weak", "json_diff", "hard", ["recursion"], DimensionScores(1.0, 0.0, 0.4, 1.0)),
    ]
    if with_disagreements:
        scores = results[3].scores
        results[3].disagreements = disagreements.detect(scores)
    aggregate.aggregate(results, config.DEFAULT_WEIGHTS)
    metadata = RunMetadata(
        provider="mock",
        models=["mock-strong", "mock-weak"],
        judge_model="mock-judge",
        corpus_count=20,
        tier_counts={"easy": 5, "medium": 5, "hard": 5},
        weights=dict(config.DEFAULT_WEIGHTS),
        thresholds=dict(config.DEFAULT_THRESHOLDS),
        temperature=0.0,
        mock=True,
        inconclusive=inconclusive,
        inconclusive_reason="every model scored identically" if inconclusive else None,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:02:00+00:00",
        duration_s=120.0,
    )
    return RunResults(metadata=metadata, results=results)


# --- 6.1 serialization -------------------------------------------------------


def test_results_round_trip_through_disk(tmp_path):
    run = _run()
    path = tmp_path / "nested" / "results.json"
    reporting.save_results(run, path)
    assert path.exists()
    loaded = reporting.load_results(path)
    assert loaded == run


def test_saved_file_is_self_describing(tmp_path):
    path = tmp_path / "results.json"
    reporting.save_results(_run(), path)
    payload = json.loads(path.read_text())
    assert payload["schema_version"] == 3
    assert payload["metadata"]["schema_name"] == config.RESULTS_SCHEMA_NAME
    assert payload["metadata"]["weights"] == config.DEFAULT_WEIGHTS
    assert payload["metadata"]["thresholds"] == config.DEFAULT_THRESHOLDS
    assert payload["metadata"]["tier_counts"]["hard"] == 5
    assert len(payload["results"]) == 4


def test_report_needs_nothing_but_the_results_file(tmp_path):
    run = _run()
    path = tmp_path / "results.json"
    reporting.save_results(run, path)
    loaded = reporting.load_results(path)
    report = reporting.render_report(loaded)
    assert "Code-generation model evaluation" in report


# --- 6.2 report structure ----------------------------------------------------


def test_report_documents_every_dimension_and_its_limits():
    report = reporting.render_report(_run())
    for dimension in ("execution", "edge", "semantic", "style"):
        assert dimension in report
    assert "### Limitations of each method" in report
    assert "Self-preference" in report
    assert "finite" in report


def test_report_includes_metadata():
    report = reporting.render_report(_run())
    assert "## Run metadata" in report
    assert "mock-judge" in report
    assert "2026-01-01T00:00:00+00:00" in report
    assert "corpus:** 20 specs" in report


def test_report_includes_model_by_dimension_table():
    report = reporting.render_report(_run())
    assert "## Model comparison" in report
    assert "| Model | Composite | execution | edge | semantic | style | n | excl |" in report
    assert "mock-strong" in report
    assert "mock-weak" in report


def test_report_includes_model_by_tier_table():
    report = reporting.render_report(_run())
    assert "## Performance by difficulty tier" in report
    assert "| Model | Tier | Composite |" in report
    assert "| `mock-strong` | easy |" in report
    assert "| `mock-weak` | hard |" in report


def test_report_ranks_models():
    report = reporting.render_report(_run())
    strong = report.index("`mock-strong`")
    weak = report.index("`mock-weak`")
    assert strong < weak


def test_mock_run_is_labelled():
    report = reporting.render_report(_run())
    assert "Mock run." in report
    assert "not a comparison of real models" in report


def test_inconclusive_run_is_flagged():
    report = reporting.render_report(_run(inconclusive=True))
    assert "inconclusive" in report
    assert "no ranking is meaningful" in report


# --- 6.3 strengths and weaknesses by task type -------------------------------


def test_report_summarises_strengths_and_weaknesses_by_task_type():
    report = reporting.render_report(_run())
    assert "## Strengths and weaknesses by task type" in report
    assert "### `mock-strong`" in report
    assert "**Strongest:**" in report
    assert "**Weakest:**" in report


def test_task_type_section_uses_spec_tags():
    report = reporting.render_report(_run())
    assert "algorithms" in report
    assert "recursion" in report


# --- 6.4 disagreements -------------------------------------------------------


def test_report_lists_disagreements_with_evidence():
    report = reporting.render_report(_run())
    assert "## Disagreements" in report
    assert DISAGREEMENT_FRAGILE in report
    assert "`mock-weak` × `json_diff`" in report
    assert "**dimensions:**" in report
    assert "**evidence:**" in report


def test_report_states_when_there_are_no_disagreements():
    run = _run(with_disagreements=False)
    report = reporting.render_report(run)
    assert "No cross-dimension disagreements were flagged" in report


def test_disagreement_counts_are_shown():
    report = reporting.render_report(_run())
    assert "| Kind | Count |" in report


# --- per-spec granularity ----------------------------------------------------


def test_report_contains_per_spec_table():
    report = reporting.render_report(_run())
    assert "## Per-spec results" in report
    assert "fizzbuzz" in report
    assert "json_diff" in report


# --- 6.5 offline rendering ---------------------------------------------------


def test_report_renders_with_no_network(monkeypatch, tmp_path):
    def no_network(*args, **kwargs):
        raise AssertionError("the report must not touch the network")

    monkeypatch.setattr(socket, "socket", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    path = tmp_path / "results.json"
    reporting.save_results(_run(), path)
    loaded = reporting.load_results(path)
    report = reporting.render_report(loaded)
    assert "Code-generation model evaluation" in report


def test_write_report_creates_parent_directories(tmp_path):
    run = _run()
    out = tmp_path / "deep" / "report.md"
    reporting.write_report(run, out)
    assert out.read_text().startswith("# Code-generation model evaluation")


def test_render_is_deterministic():
    run = _run()
    assert reporting.render_report(run) == reporting.render_report(run)


def test_build_run_metadata_collects_corpus_counts(tmp_path):
    from codegen_evals import corpus

    repo_root = Path(__file__).resolve().parent.parent
    specs = corpus.load_corpus(repo_root / "corpus")
    metadata = reporting.build_run_metadata(
        provider="mock",
        models=["a"],
        judge_model="j",
        specs=specs,
        weights=dict(config.DEFAULT_WEIGHTS),
        thresholds=dict(config.DEFAULT_THRESHOLDS),
        temperature=0.0,
        mock=True,
        started_at="t0",
        finished_at="t1",
        duration_s=1.0,
    )
    assert metadata.corpus_count == 20
    assert metadata.tier_counts == {"easy": 5, "medium": 5, "hard": 10}
