"""Tests for isolated execution and JUnit evidence parsing."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from codegen_evals import corpus, execution

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_ROOT = REPO_ROOT / "corpus"


def _spec(spec_id: str):
    return corpus.load_corpus(CORPUS_ROOT, ids=[spec_id])[0]


def _temp_spec(tmp_path: Path, solution: str, ground_truth: str, edge: str = "def test_ok():\n    assert True\n"):
    spec_dir = tmp_path / "tempid"
    spec_dir.mkdir()
    payload = {
        "id": "tempid",
        "tier": "easy",
        "tags": ["testing"],
        "prompt": "do a thing",
        "required_symbols": ["f"],
    }
    (spec_dir / "spec.json").write_text(json.dumps(payload), encoding="utf-8")
    (spec_dir / "solution.py").write_text(solution, encoding="utf-8")
    (spec_dir / "test_ground_truth.py").write_text(ground_truth, encoding="utf-8")
    (spec_dir / "test_edge_cases.py").write_text(edge, encoding="utf-8")
    return corpus.load_spec(spec_dir)


# --- 4.1 / 4.2 execution and evidence ---------------------------------------


def test_reference_passes_its_ground_truth_suite():
    spec = _spec("fizzbuzz")
    evidence = execution.run_suite(spec, corpus.solution_source(spec), "ground_truth")
    assert evidence.setup_error is None
    assert evidence.total == 5
    assert evidence.failed == []
    assert len(evidence.passed) == 5
    assert evidence.fraction == 1.0


def test_partial_failure_is_recorded_with_messages():
    spec = _spec("fizzbuzz")
    broken = "def fizzbuzz(n):\n    return ['wrong'] * n\n"
    evidence = execution.run_suite(spec, broken, "ground_truth")
    assert evidence.failed
    assert evidence.passed_count < evidence.total
    assert all(message for message in evidence.messages.values())


def test_import_error_is_contained_in_evidence():
    spec = _spec("fizzbuzz")
    evidence = execution.run_suite(spec, "raise RuntimeError('boom')\n", "ground_truth")
    assert evidence.passed == []
    assert evidence.failed or evidence.setup_error


def test_skipped_test_is_not_counted_as_passed(tmp_path):
    spec = _temp_spec(
        tmp_path,
        solution="def f():\n    return 1\n",
        ground_truth="import pytest\n\n\ndef test_skip():\n    pytest.skip('nope')\n",
    )
    evidence = execution.run_suite(spec, "def f():\n    return 1\n", "ground_truth")
    assert evidence.total == 1
    assert evidence.passed == []
    assert evidence.failed


def test_unknown_suite_is_rejected():
    spec = _spec("fizzbuzz")
    with pytest.raises(ValueError):
        execution.run_suite(spec, "x = 1\n", "not_a_suite")


# --- 4.3 timeout and crash handling -----------------------------------------


def test_timeout_is_enforced():
    spec = _spec("fizzbuzz")
    code = "def fizzbuzz(n):\n    while True:\n        pass\n"
    started = time.monotonic()
    evidence = execution.run_suite(spec, code, "ground_truth", timeout_s=3.0)
    assert evidence.timed_out is True
    assert evidence.setup_error is not None
    assert time.monotonic() - started < 45


def test_crash_does_not_prevent_later_candidates():
    spec = _spec("fizzbuzz")
    crashed = execution.run_suite(spec, "raise SystemExit(1)\n", "ground_truth")
    good = execution.run_suite(spec, corpus.solution_source(spec), "ground_truth")
    assert crashed.failed or crashed.setup_error
    assert good.failed == []
    assert good.fraction == 1.0


# --- 4.4 separate suites ----------------------------------------------------


def test_both_suites_run_separately():
    spec = _spec("fizzbuzz")
    ground_truth, edge_case = execution.run_spec(spec, corpus.solution_source(spec))
    assert ground_truth.suite == "ground_truth"
    assert edge_case.suite == "edge_case"
    assert ground_truth is not edge_case
    assert ground_truth.failed == []
    assert edge_case.failed == []


def test_evidence_is_distinct_per_suite():
    spec = _spec("word_freq")
    ground_truth, edge_case = execution.run_spec(spec, corpus.solution_source(spec))
    assert ground_truth.total != edge_case.total or ground_truth is not edge_case


def test_missing_suite_file_is_reported(tmp_path):
    spec = _temp_spec(
        tmp_path,
        solution="def f():\n    return 1\n",
        ground_truth="def test_ok():\n    assert True\n",
    )
    Path(spec.path, "test_edge_cases.py").unlink()
    evidence = execution.run_suite(spec, "def f():\n    return 1\n", "edge_case")
    assert evidence.setup_error is not None
    assert evidence.total == 0


# --- 4.5 fault containment / 2.6 self-validation ----------------------------


def test_problems_for_lists_failed_tests():
    spec = _spec("fizzbuzz")
    evidence = execution.run_suite(spec, "def fizzbuzz(n):\n    return []\n", "ground_truth")
    problems = execution.problems_for(evidence)
    assert problems
    assert any("::" in problem for problem in problems)


def test_validate_soundness_passes_on_shipped_corpus():
    specs = corpus.load_corpus(CORPUS_ROOT)
    rows = corpus.validate_soundness(specs)
    failures = [row for row in rows if not row["ok"]]
    assert failures == [], failures
    assert len(rows) == len(specs) * 2


def test_validate_soundness_reports_a_broken_reference(tmp_path):
    spec = _temp_spec(
        tmp_path,
        solution="def f():\n    return 'wrong'\n",
        ground_truth="from solution import f\n\n\ndef test_f():\n    assert f() == 1\n",
    )
    rows = corpus.validate_soundness([spec])
    broken = [row for row in rows if not row["ok"]]
    assert broken
    assert any(row["spec_id"] == "tempid" for row in broken)
    assert any(row["suite"] == "ground_truth" for row in broken)
    assert any(row["problems"] for row in broken)


def test_check_spec_soundness_returns_problems_for_broken_spec(tmp_path):
    spec = _temp_spec(
        tmp_path,
        solution="def f():\n    return 'wrong'\n",
        ground_truth="from solution import f\n\n\ndef test_f():\n    assert f() == 1\n",
    )
    problems = corpus.check_spec_soundness(spec)
    assert problems
    assert any("ground_truth" in problem for problem in problems)


def test_check_spec_soundness_passes_for_reference(tmp_path):
    spec = _temp_spec(
        tmp_path,
        solution="def f():\n    return 1\n",
        ground_truth="from solution import f\n\n\ndef test_f():\n    assert f() == 1\n",
    )
    assert corpus.check_spec_soundness(spec) == []
