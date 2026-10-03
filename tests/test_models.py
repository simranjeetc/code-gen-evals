"""Round-trip tests for the shared dataclasses."""

from __future__ import annotations

from codegen_evals.models import (
    SCHEMA_VERSION,
    DimensionScores,
    Disagreement,
    EvalResult,
    ExecutionEvidence,
    Generation,
    RunMetadata,
    RunResults,
    Spec,
)


def test_schema_version_is_stable():
    assert SCHEMA_VERSION == 1


def test_spec_round_trip():
    spec = Spec(
        id="fizzbuzz",
        tier="easy",
        tags=["algorithms"],
        prompt="Write fizzbuzz.",
        entrypoint="solution",
        required_symbols=["fizzbuzz"],
        title="FizzBuzz",
        path="/tmp/fizzbuzz",
    )
    assert Spec.from_dict(spec.to_dict()) == spec


def test_spec_from_dict_ignores_unknown_and_defaults_missing():
    data = {"id": "x", "tier": "easy", "tags": [], "prompt": "p", "unexpected": 1}
    spec = Spec.from_dict(data)
    assert spec.id == "x"
    assert spec.required_symbols == []


def test_generation_round_trip():
    gen = Generation(
        model_id="opencode-go/mimo-v2.6-flash",
        provider="opencode",
        spec_id="fizzbuzz",
        raw_text="```python\nx = 1\n```",
        code="x = 1\n",
        extracted=True,
        duration_s=1.5,
        params={"temperature": 0.0},
    )
    assert Generation.from_dict(gen.to_dict()) == gen


def test_execution_evidence_fraction_and_round_trip():
    ev = ExecutionEvidence(
        suite="ground_truth",
        total=4,
        passed=["a", "b", "c"],
        failed=["d"],
        messages={"d": "boom"},
        duration_s=0.2,
        returncode=1,
    )
    assert ev.fraction == 0.75
    restored = ExecutionEvidence.from_dict(ev.to_dict())
    assert restored.passed == ["a", "b", "c"]
    assert restored.messages == {"d": "boom"}
    assert restored.fraction == 0.75


def test_execution_evidence_fraction_zero_when_no_tests():
    assert ExecutionEvidence(suite="edge_case", total=0).fraction == 0.0


def test_dimension_scores_allow_abstained_semantic():
    scores = DimensionScores(execution=1.0, edge=0.5, style=0.9, semantic=None)
    restored = DimensionScores.from_dict(scores.to_dict())
    assert restored.semantic is None
    assert restored.execution == 1.0
    assert restored.edge == 0.5


def test_disagreement_round_trip():
    d = Disagreement(
        kind="passes_visible_fails_edges",
        dimensions=["execution", "edge"],
        detail="passed ground truth, failed edges",
        evidence={"execution": 1.0, "edge": 0.25},
    )
    assert Disagreement.from_dict(d.to_dict()) == d


def test_eval_result_round_trip_with_nested_evidence():
    result = EvalResult(
        model_id="m",
        provider="mock",
        spec_id="s",
        tier="hard",
        tags=["concurrency"],
        scores=DimensionScores(execution=0.5, edge=0.0, style=0.75, semantic=0.4),
        composite=0.42,
        ground_truth=ExecutionEvidence(suite="ground_truth", total=2, passed=["t1"], failed=["t2"]),
        edge_case=ExecutionEvidence(suite="edge_case", total=2, failed=["e1", "e2"]),
        extraction_ok=True,
        disagreements=[
            Disagreement(kind="x", dimensions=["execution"], detail="d", evidence={})
        ],
    )
    restored = EvalResult.from_dict(result.to_dict())
    assert restored == result
    assert restored.ground_truth is not None
    assert restored.ground_truth.fraction == 0.5
    assert restored.edge_case is not None
    assert restored.edge_case.fraction == 0.0
    assert restored.disagreements[0].kind == "x"


def test_eval_result_handles_missing_evidence():
    restored = EvalResult.from_dict({"model_id": "m", "spec_id": "s"})
    assert restored.ground_truth is None
    assert restored.edge_case is None
    assert restored.scores.execution == 0.0


def test_run_results_round_trip():
    run = RunResults(
        metadata=RunMetadata(
            provider="opencode",
            models=["a", "b"],
            judge_model="j",
            corpus_count=15,
            tier_counts={"easy": 5, "medium": 5, "hard": 5},
            weights={"execution": 0.4},
            thresholds={"high": 0.8, "low": 0.6},
            mock=False,
            inconclusive=False,
        ),
        results=[
            EvalResult(model_id="a", provider="opencode", spec_id="s1", tier="easy"),
        ],
    )
    restored = RunResults.from_dict(run.to_dict())
    assert restored == run
    assert restored.schema_version == SCHEMA_VERSION
    assert restored.metadata.tier_counts["hard"] == 5
