"""Tests for the four dimensions, aggregation, disagreements, and the guard."""

from __future__ import annotations

from codegen_evals import config
from codegen_evals.models import (
    DISAGREEMENT_FRAGILE,
    DISAGREEMENT_SEMANTIC,
    DISAGREEMENT_STYLE,
    EvalResult,
    ExecutionEvidence,
    DimensionScores,
    Spec,
)
from codegen_evals.scoring import aggregate, dimensions, disagreements, semantic, style
from codegen_evals.providers import base


def _evidence(suite, total, passed, failed=()):
    return ExecutionEvidence(
        suite=suite,
        total=total,
        passed=[f"{suite}::t{i}" for i in range(passed)],
        failed=[f"{suite}::f{i}" for i in range(len(failed))],
    )


# --- 5.1 execution and edge scores ------------------------------------------


def test_execution_score_is_the_passed_fraction():
    assert dimensions.execution_score(_evidence("ground_truth", 4, 3)) == 0.75


def test_edge_score_is_the_passed_fraction():
    assert dimensions.edge_score(_evidence("edge_case", 4, 1)) == 0.25


def test_zero_when_no_tests_ran():
    assert dimensions.execution_score(ExecutionEvidence(suite="ground_truth", total=0)) == 0.0


def test_zero_when_evidence_missing():
    assert dimensions.execution_score(None) == 0.0
    assert dimensions.edge_score(None) == 0.0


def test_zero_when_extraction_failed():
    evidence = _evidence("ground_truth", 4, 4)
    assert dimensions.execution_score(evidence, extraction_ok=False) == 0.0
    assert dimensions.edge_score(_evidence("edge_case", 4, 4), extraction_ok=False) == 0.0


def test_scores_are_bounded():
    for value in (
        dimensions.execution_score(_evidence("ground_truth", 3, 3)),
        dimensions.execution_score(_evidence("ground_truth", 3, 0)),
    ):
        assert 0.0 <= value <= 1.0


def test_full_pass_is_one():
    assert dimensions.execution_score(_evidence("ground_truth", 5, 5)) == 1.0


# --- 5.2 style ---------------------------------------------------------------


GOOD_STYLE = '''"""Module docstring."""


def add(first: int, second: int) -> int:
    """Add two numbers."""
    return first + second
'''


BAD_STYLE = '''def add(a, b):
    if a:
        try:
            return a + b
        except:
            pass
    return b
'''


def test_good_style_scores_high():
    score, details = style.analyze_style(GOOD_STYLE)
    assert score > 0.9
    assert details["checks"]["annotations"] == 1.0
    assert details["checks"]["docstrings"] == 1.0
    assert details["checks"]["bare_except"] == 1.0


def test_bad_style_scores_lower():
    good, _ = style.analyze_style(GOOD_STYLE)
    bad, details = style.analyze_style(BAD_STYLE)
    assert bad < good
    assert details["checks"]["annotations"] < 1.0
    assert details["checks"]["docstrings"] < 1.0
    assert details["checks"]["bare_except"] == 0.0


def test_style_is_deterministic():
    first, _ = style.analyze_style(GOOD_STYLE)
    second, _ = style.analyze_style(GOOD_STYLE)
    assert first == second


def test_style_reports_per_check_outcomes():
    _, details = style.analyze_style(GOOD_STYLE)
    assert set(details["checks"]) >= {
        "parseable",
        "annotations",
        "docstrings",
        "naming",
        "line_length",
        "complexity",
        "bare_except",
    }


def test_unparseable_source_scores_zero():
    score, details = style.analyze_style("def broken(:\n")
    assert score == 0.0
    assert details["notes"]


def test_empty_source_scores_zero():
    assert style.analyze_style("")[0] == 0.0
    assert style.analyze_style(None)[0] == 0.0


def test_long_lines_reduce_line_length_check():
    long_source = "x = 1  # " + "y" * 200 + "\n"
    _, details = style.analyze_style(long_source)
    assert details["checks"]["line_length"] < 1.0


def test_high_complexity_reduces_complexity_check():
    branches = "\n".join(f"    if x == {i}:\n        pass" for i in range(15))
    source = f"def f(x):\n{branches}\n    return x\n"
    _, details = style.analyze_style(source)
    assert details["checks"]["complexity"] < 1.0
    assert details["max_complexity"] > 10


def test_non_snake_case_names_reduce_naming_check():
    source = "def doThing():\n    return 1\n"
    _, details = style.analyze_style(source)
    assert details["checks"]["naming"] < 1.0


def test_ruff_is_opt_in_and_absent_by_default():
    _, details = style.analyze_style(GOOD_STYLE)
    assert details["ruff"] is None
    assert "ruff" not in details["checks"]


def test_ruff_blend_used_when_requested():
    def fake_ruff(source):
        return {"findings": 3, "rules": ["E501"]}

    score, details = style.analyze_style(GOOD_STYLE, use_ruff=True, ruff_runner=fake_ruff)
    assert details["checks"]["ruff"] == 0.0
    assert score < 1.0


def test_ruff_unavailable_is_noted_and_skipped():
    score, details = style.analyze_style(GOOD_STYLE, use_ruff=True, ruff_runner=lambda source: None)
    assert details["ruff"] is None
    assert any("ruff" in note for note in details["notes"])


# --- 5.3 semantic judge ------------------------------------------------------


class _FakeProvider:
    name = "fake"

    def __init__(self, text="", error=None):
        self._text = text
        self._error = error
        self.calls = []

    def generate(self, prompt, model_id, spec_id=""):
        self.calls.append((prompt, model_id, spec_id))
        from codegen_evals.models import Generation

        generation = Generation(model_id=model_id, provider="fake", spec_id=spec_id)
        if self._error:
            generation.error = self._error
            return generation
        generation.raw_text = self._text
        generation.extracted = True
        generation.code = "x = 1\n"
        return generation

    def generate_text(self, prompt, model_id, spec_id=""):
        return self.generate(prompt, model_id, spec_id)


def _spec_obj():
    return Spec(id="fizzbuzz", tier="easy", tags=["algorithms"], prompt="Write fizzbuzz.", required_symbols=["fizzbuzz"])


def test_parse_verdict_accepts_clean_json():
    assert semantic.parse_verdict('{"score": 0.75, "rationale": "ok"}')["score"] == 0.75


def test_parse_verdict_accepts_json_embedded_in_prose():
    parsed = semantic.parse_verdict('Sure! {"score": 1, "rationale": "good"} done')
    assert parsed["score"] == 1.0


def test_parse_verdict_rejects_garbage():
    assert semantic.parse_verdict("no json here") is None
    assert semantic.parse_verdict("") is None
    assert semantic.parse_verdict('{"rationale": "no score"}') is None


def test_parse_verdict_clamps_out_of_range_scores():
    assert semantic.parse_verdict('{"score": 5}')["score"] == 1.0
    assert semantic.parse_verdict('{"score": -3}')["score"] == 0.0


def test_judge_scores_from_provider_text():
    provider = _FakeProvider(text='{"score": 0.5, "rationale": "half right"}')
    judge = semantic.ProviderJudge(provider, "judge-model")
    verdict = judge.judge(_spec_obj(), "prompt", "x = 1\n", "subject-model")
    assert verdict.score == 0.5
    assert verdict.rationale == "half right"
    assert verdict.judge_model == "judge-model"


def test_judge_abstains_on_unparseable_output():
    provider = _FakeProvider(text="I think it is fine.")
    judge = semantic.ProviderJudge(provider, "judge-model")
    verdict = judge.judge(_spec_obj(), "prompt", "x = 1\n", "subject-model")
    assert verdict.score is None
    assert verdict.abstained is True
    assert verdict.error


def test_judge_abstains_on_provider_error():
    provider = _FakeProvider(error="TimeoutError: boom")
    judge = semantic.ProviderJudge(provider, "judge-model")
    verdict = judge.judge(_spec_obj(), "prompt", "x = 1\n", "subject-model")
    assert verdict.score is None
    assert "boom" in verdict.error


def test_judge_refuses_to_grade_itself():
    provider = _FakeProvider(text='{"score": 1.0, "rationale": "great"}')
    judge = semantic.ProviderJudge(provider, "same-model")
    verdict = judge.judge(_spec_obj(), "prompt", "x = 1\n", "same-model")
    assert verdict.score is None
    assert "self-grade" in verdict.error
    assert provider.calls == []


def test_judge_scores_missing_code_as_zero_without_calling_the_model():
    provider = _FakeProvider(text='{"score": 1.0, "rationale": "great"}')
    judge = semantic.ProviderJudge(provider, "judge-model")
    verdict = judge.judge(_spec_obj(), "prompt", None, "subject-model")
    assert verdict.score == 0.0
    assert provider.calls == []


def test_judge_prompt_contains_requirement_and_code():
    prompt = semantic.build_prompt(
        "Write fizzbuzz.", "def fizzbuzz(n):\n    return n\n", "def fizzbuzz(n): ..."
    )
    assert "Write fizzbuzz." in prompt
    assert "def fizzbuzz(n): ..." in prompt
    assert "def fizzbuzz(n):\n    return n" in prompt  # the reference anchor
    assert "REFERENCE SOLUTION" in prompt
    assert "CANDIDATE SOLUTION" in prompt
    assert "Ignore style" in prompt


def test_judge_uses_raw_text_not_code_extraction():
    """Regression: the judge returns raw JSON, not a fenced block.

    ``Provider.generate`` requires extractable code and would discard the judge's
    response before it could be parsed.
    """

    class RawJsonProvider(base.Provider):
        name = "raw-json"

        def _invoke(self, prompt, model_id, spec_id="", timeout_s=None):
            return '{"score": 0.25, "rationale": "partly there"}', {}

    provider = RawJsonProvider()
    assert provider.generate("p", "m").extracted is False
    assert provider.generate_text("p", "m").extracted is True

    judge = semantic.ProviderJudge(provider, "judge-model")
    verdict = judge.judge(_spec_obj(), "prompt", "x = 1\n", "subject-model")
    assert verdict.score == 0.25
    assert verdict.rationale == "partly there"


def test_generate_text_does_not_reinterpret_code_as_a_verdict():
    class MixedProvider(base.Provider):
        name = "mixed"

        def _invoke(self, prompt, model_id, spec_id="", timeout_s=None):
            return 'Here you go:\n```python\nx = 1\n```\n{"score": 0.75}', {}

    provider = MixedProvider()
    generation = provider.generate_text("p", "m")
    assert generation.code is None
    judge = semantic.ProviderJudge(provider, "judge-model")
    verdict = judge.judge(_spec_obj(), "prompt", "x = 1\n", "subject-model")
    assert verdict.score == 0.75


def test_mock_judge_is_deterministic_and_produces_disagreements():
    variants = {"mock-strong": "perfect", "mock-weak": "empty"}

    def lookup(model_id, spec_id):
        return variants[model_id]

    judge = semantic.MockJudge(lookup)
    first = judge.judge(_spec_obj(), "p", "x = 1\n", "mock-strong")
    second = judge.judge(_spec_obj(), "p", "x = 1\n", "mock-strong")
    assert first.score == second.score


# --- 5.4 aggregation ---------------------------------------------------------


def _result(model_id, spec_id, tier, scores, tags=("algorithms",)):
    return EvalResult(
        model_id=model_id,
        provider="mock",
        spec_id=spec_id,
        tier=tier,
        tags=list(tags),
        scores=scores,
    )


def test_composite_is_weighted_average():
    scores = DimensionScores(execution=1.0, edge=0.5, style=0.0, semantic=0.0)
    weights = {"execution": 0.5, "edge": 0.5}
    assert aggregate.composite(scores, weights) == 0.75


def test_composite_renormalises_over_available_dimensions():
    scores = DimensionScores(execution=1.0, edge=1.0, style=1.0, semantic=None)
    weights = {"execution": 0.5, "semantic": 0.5}
    assert aggregate.composite(scores, weights) == 1.0


def test_composite_is_none_when_nothing_available():
    scores = DimensionScores(execution=0.0, edge=0.0, style=0.0, semantic=None)
    assert aggregate.composite(scores, {"semantic": 1.0}) is None


def test_aggregate_by_model_dimension_and_tier():
    results = [
        _result("a", "s1", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0)),
        _result("a", "s2", "hard", DimensionScores(0.0, 0.0, 0.0, 0.0)),
        _result("b", "s1", "easy", DimensionScores(0.5, 0.5, 0.5, 0.5)),
    ]
    summary = aggregate.aggregate(results, {"execution": 1.0})
    assert summary["by_model"]["a"]["execution"] == 0.5
    assert summary["by_model"]["a"]["n"] == 2
    assert summary["by_model"]["b"]["execution"] == 0.5
    assert summary["by_tier"]["a"]["easy"]["execution"] == 1.0
    assert summary["by_tier"]["a"]["hard"]["execution"] == 0.0
    assert summary["by_model"]["a"]["composite"] == 0.5


def test_aggregate_by_task_type():
    results = [
        _result("a", "s1", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0), tags=("parsing",)),
        _result("a", "s2", "easy", DimensionScores(0.0, 0.0, 0.0, 0.0), tags=("concurrency",)),
        _result("a", "s3", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0), tags=("parsing", "concurrency")),
    ]
    summary = aggregate.aggregate(results, {"execution": 1.0})
    assert summary["by_task_type"]["a"]["parsing"]["n"] == 2
    assert summary["by_task_type"]["a"]["parsing"]["composite"] == 1.0
    assert summary["by_task_type"]["a"]["concurrency"]["composite"] == 0.5


def test_weights_are_configurable():
    results = [_result("a", "s1", "easy", DimensionScores(1.0, 0.0, 0.0, 0.0))]
    execution_heavy = aggregate.aggregate(results, {"execution": 1.0})["by_model"]["a"]["composite"]
    edge_heavy = aggregate.aggregate(results, {"edge": 1.0})["by_model"]["a"]["composite"]
    assert execution_heavy == 1.0
    assert edge_heavy == 0.0


def test_ranking_is_ordered_by_composite():
    results = [
        _result("low", "s1", "easy", DimensionScores(0.1, 0.1, 0.1, 0.1)),
        _result("high", "s1", "easy", DimensionScores(0.9, 0.9, 0.9, 0.9)),
    ]
    summary = aggregate.aggregate(results, {"execution": 1.0})
    assert [row["model_id"] for row in summary["ranking"]] == ["high", "low"]


def test_semantic_abstentions_are_counted_not_averaged_in():
    results = [
        _result("a", "s1", "easy", DimensionScores(1.0, 1.0, 1.0, None)),
        _result("a", "s2", "easy", DimensionScores(0.0, 0.0, 0.0, 1.0)),
    ]
    summary = aggregate.aggregate(results, {"execution": 1.0})
    assert summary["by_model"]["a"]["semantic"] == 1.0
    assert summary["by_model"]["a"]["semantic_abstentions"] == 1


def test_task_type_extremes():
    results = [
        _result("a", "s1", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0), tags=("parsing",)),
        _result("a", "s2", "easy", DimensionScores(0.0, 0.0, 0.0, 0.0), tags=("graphs",)),
    ]
    summary = aggregate.aggregate(results, {"execution": 1.0})
    best, worst = aggregate.task_type_extremes(summary["by_task_type"], "a")
    assert best[0] == "parsing"
    assert worst[0] == "graphs"


# --- 5.5 disagreements -------------------------------------------------------


def test_green_tests_wrong_semantics_is_flagged():
    scores = DimensionScores(execution=1.0, edge=1.0, style=1.0, semantic=0.2)
    kinds = {item.kind for item in disagreements.detect(scores)}
    assert DISAGREEMENT_SEMANTIC in kinds


def test_fragile_pass_is_flagged():
    scores = DimensionScores(execution=1.0, edge=0.1, style=1.0, semantic=1.0)
    kinds = {item.kind for item in disagreements.detect(scores)}
    assert DISAGREEMENT_FRAGILE in kinds


def test_correct_but_unidiomatic_is_flagged():
    scores = DimensionScores(execution=1.0, edge=1.0, style=0.2, semantic=1.0)
    kinds = {item.kind for item in disagreements.detect(scores)}
    assert DISAGREEMENT_STYLE in kinds


def test_no_disagreement_when_everything_is_good():
    scores = DimensionScores(execution=1.0, edge=1.0, style=1.0, semantic=1.0)
    assert disagreements.detect(scores) == []


def test_no_disagreement_when_everything_is_bad():
    scores = DimensionScores(execution=0.0, edge=0.0, style=0.0, semantic=0.0)
    assert disagreements.detect(scores) == []


def test_thresholds_are_configurable():
    scores = DimensionScores(execution=0.7, edge=1.0, style=1.0, semantic=0.55)
    assert disagreements.detect(scores, high=0.8, low=0.6) == []
    assert disagreements.detect(scores, high=0.65, low=0.6)
    assert disagreements.detect(scores, high=0.8, low=0.5) == []


def test_style_disagreement_records_failing_checks():
    scores = DimensionScores(
        execution=1.0,
        edge=1.0,
        style=0.2,
        semantic=1.0,
        style_checks={"annotations": 0.0, "naming": 1.0},
    )
    item = disagreements.detect(scores)[0]
    assert item.evidence["failing_checks"] == {"annotations": 0.0}


def test_disagreements_are_attached_to_results():
    scores = DimensionScores(execution=1.0, edge=0.0, style=1.0, semantic=1.0)
    result = EvalResult(model_id="a", spec_id="s", tier="easy", scores=scores)
    result.disagreements = disagreements.detect(scores)
    assert result.disagreements
    assert result.to_dict()["disagreements"][0]["kind"] == DISAGREEMENT_FRAGILE


def test_summarise_counts_by_kind():
    scores = DimensionScores(execution=1.0, edge=0.1, style=0.1, semantic=0.1)
    counts = disagreements.summarise(disagreements.detect(scores))
    assert counts[DISAGREEMENT_FRAGILE] == 1


def test_thresholds_from_config():
    assert disagreements.thresholds_from_config(config) == config.DEFAULT_THRESHOLDS


# --- 5.6 degenerate-run guard ------------------------------------------------


def test_uniform_all_perfect_run_is_degenerate():
    results = [
        _result(model, "s1", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0))
        for model in ("a", "b")
    ]
    reason = aggregate.degenerate_reason(results)
    assert reason is not None
    assert "perfectly" in reason


def test_uniform_all_zero_run_is_degenerate():
    results = [
        _result(model, "s1", "easy", DimensionScores(0.0, 0.0, 0.0, 0.0))
        for model in ("a", "b")
    ]
    reason = aggregate.degenerate_reason(results)
    assert reason is not None
    assert "zero" in reason


def test_uniform_but_not_extreme_run_is_degenerate():
    scores = DimensionScores(0.5, 0.5, 0.5, 0.5)
    results = [_result(model, "s1", "easy", scores) for model in ("a", "b")]
    assert aggregate.degenerate_reason(results) is not None


def test_differentiated_run_is_not_degenerate():
    results = [
        _result("a", "s1", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0)),
        _result("b", "s1", "easy", DimensionScores(0.4, 0.2, 0.9, 0.5)),
    ]
    assert aggregate.degenerate_reason(results) is None


def test_difference_on_a_single_spec_is_enough():
    results = [
        _result("a", "s1", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0)),
        _result("b", "s1", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0)),
        _result("a", "s2", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0)),
        _result("b", "s2", "easy", DimensionScores(1.0, 0.5, 1.0, 1.0)),
    ]
    assert aggregate.degenerate_reason(results) is None


def test_single_model_is_never_degenerate():
    results = [_result("a", "s1", "easy", DimensionScores(1.0, 1.0, 1.0, 1.0))]
    assert aggregate.degenerate_reason(results) is None


def test_empty_results_are_reported():
    assert aggregate.degenerate_reason([]) is not None
