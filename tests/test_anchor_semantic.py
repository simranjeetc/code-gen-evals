"""Reference-anchored judging, the objective-only composite, judge agreement,
and the report's treatment of the semantic dimension as an opinion.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codegen_evals import config, corpus, pipeline, reporting
from codegen_evals.models import (
    OBJECTIVE_DIMENSIONS,
    DimensionScores,
    EvalResult,
    RunMetadata,
    RunResults,
)
from codegen_evals.providers import base
from codegen_evals.scoring import aggregate, semantic

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_ROOT = REPO_ROOT / "corpus"


def _spec(spec_id: str = "fizzbuzz"):
    return corpus.load_corpus(CORPUS_ROOT, ids=[spec_id])[0]


class _StaticProvider(base.Provider):
    name = "static"

    def __init__(self, code: str):
        super().__init__()
        self._code = code

    def _invoke(self, prompt, model_id, spec_id="", timeout_s=None):
        return "```python\n" + self._code + "```", {}


class _RecordingJudge(semantic.SemanticJudge):
    judge_model = "recording-judge"

    def __init__(self, score: float = 1.0):
        self.score = score
        self.calls = []

    def judge(self, spec, prompt, code, subject_model, reference=None):
        self.calls.append(
            {"prompt": prompt, "code": code, "reference": reference, "subject": subject_model}
        )
        return semantic.JudgeVerdict(
            score=self.score, rationale="because", judge_model=self.judge_model
        )


# --- 1.1 - 1.3 the prompt is anchored, banded, and warned -------------------


def test_judge_prompt_contains_requirement_reference_and_candidate():
    prompt = semantic.build_prompt(
        "Write add(a, b).", "def add(a, b):\n    return a + b\n", "def add(a, b):\n    return a - b\n"
    )
    assert "Write add(a, b)." in prompt
    assert "def add(a, b):\n    return a + b" in prompt
    assert "def add(a, b):\n    return a - b" in prompt
    assert "REFERENCE SOLUTION" in prompt
    assert "CANDIDATE SOLUTION" in prompt
    assert "anchor" in prompt


def test_judge_prompt_is_byte_identical_across_calls():
    args = ("Requirement.", "def f():\n    return 1\n", "def f():\n    return 2\n")
    assert semantic.build_prompt(*args) == semantic.build_prompt(*args)


def test_judge_prompt_defines_all_three_score_bands():
    prompt = semantic.build_prompt("r", "def f():\n    return 1\n", "def f():\n    return 2\n")
    for marker in ("1.0", "0.5", "0.0"):
        assert marker in prompt


def test_judge_prompt_warns_against_superficial_similarity():
    prompt = semantic.build_prompt("r", "def f():\n    return 1\n", "def f():\n    return 2\n")
    assert "superficial" in prompt.lower()


# --- 1.4 - 1.5 the reference reaches the judge and not the subject ----------


class _CaptureJudgeProvider(base.Provider):
    name = "capture"

    def __init__(self):
        super().__init__()
        self.prompts = []

    def _invoke(self, prompt, model_id, spec_id="", timeout_s=None):
        self.prompts.append(prompt)
        return '{"score": 1.0, "rationale": "ok"}', {}


def test_pipeline_threads_the_reference_into_the_judge_prompt():
    spec = _spec("fizzbuzz")
    reference = corpus.solution_source(spec)
    provider = _CaptureJudgeProvider()
    judge = semantic.ProviderJudge(provider, "judge-x")
    result = pipeline.evaluate_pair(
        spec=spec,
        model_id="m",
        provider=_StaticProvider(reference),
        judge=judge,
        weights=dict(config.DEFAULT_WEIGHTS),
        thresholds=dict(config.DEFAULT_THRESHOLDS),
        suite_timeout_s=30.0,
    )
    assert result.scores.semantic == 1.0
    assert len(provider.prompts) == 1
    assert reference.strip() in provider.prompts[0]
    assert "REFERENCE SOLUTION" in provider.prompts[0]


def test_reference_is_never_sent_to_the_subject():
    for spec in corpus.load_corpus(CORPUS_ROOT):
        reference = corpus.solution_source(spec).strip()
        subject_prompt = corpus.render_prompt(spec)
        assert reference not in subject_prompt
        assert "solution.py" not in subject_prompt


# --- 2.1 - 2.4 objective-only composite -------------------------------------


def test_composite_weights_are_objective_only_and_sum_to_one():
    assert set(config.DEFAULT_WEIGHTS) == set(OBJECTIVE_DIMENSIONS)
    assert abs(sum(config.DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


def test_semantic_is_not_blended_into_the_composite():
    a = DimensionScores(execution=0.8, edge=0.8, style=0.8, semantic=0.0)
    b = DimensionScores(execution=0.8, edge=0.8, style=0.8, semantic=1.0)
    assert aggregate.composite(a, config.DEFAULT_WEIGHTS) == aggregate.composite(
        b, config.DEFAULT_WEIGHTS
    )


def test_semantic_is_still_aggregated_and_abstentions_counted():
    results = [
        EvalResult(
            model_id="a",
            spec_id="s1",
            tier="easy",
            scores=DimensionScores(1.0, 1.0, 1.0, 0.5),
        ),
        EvalResult(
            model_id="a",
            spec_id="s2",
            tier="easy",
            scores=DimensionScores(1.0, 1.0, 1.0, None),
        ),
    ]
    summary = aggregate.aggregate(results, dict(config.DEFAULT_WEIGHTS))["by_model"]["a"]
    assert summary["semantic"] == 0.5
    assert summary["semantic_abstentions"] == 1
    # composite is over objective dimensions, unaffected by semantic
    assert summary["composite"] == pytest.approx(1.0)


def test_semantic_is_marked_judge_derived_and_round_trips():
    scores = DimensionScores(execution=1.0, semantic=0.7, semantic_derived=True)
    payload = scores.to_dict()
    assert payload["semantic_derived"] is True
    assert DimensionScores.from_dict(payload).semantic_derived is True


# --- 3.1 - 3.3 judge agreement ----------------------------------------------


def test_judge_agreement_emits_exact_match_and_mean_absolute_difference():
    from codegen_evals.scoring import judge_agreement

    specs = corpus.load_corpus(CORPUS_ROOT, ids=["fizzbuzz", "word_freq"])
    judges = [("judge-a", _RecordingJudge(1.0)), ("judge-b", _RecordingJudge(0.5))]
    result = judge_agreement.measure(specs, judges)
    assert result["n"] == 2
    assert result["exact_match_rate"] == 0.0
    assert result["mean_absolute_difference"] == pytest.approx(0.5)


def test_judge_agreement_records_abstentions_as_incomparable():
    from codegen_evals.scoring import judge_agreement

    specs = corpus.load_corpus(CORPUS_ROOT, ids=["fizzbuzz", "word_freq"])
    judges = [("judge-a", _RecordingJudge(1.0)), ("judge-b", _RecordingJudge(1.0))]
    judges[1][1].score = None  # type: ignore[assignment]
    result = judge_agreement.measure(specs, judges)
    assert result["n"] == 0
    assert result["exact_match_rate"] is None


def test_judge_agreement_cli_runs_and_emits_both_figures(capsys):
    from codegen_evals import cli

    exit_code = cli.main(
        [
            "judge-agreement",
            "--provider",
            "mock",
            "--specs",
            "fizzbuzz,word_freq",
            "--judges",
            "judge-a,judge-b",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == cli.EXIT_OK
    assert payload["n"] == 2
    assert "exact_match_rate" in payload
    assert "mean_absolute_difference" in payload


def _run(agreement=None, reference_baseline=None, schema_version=None, judge_design=None):
    results = [
        EvalResult(
            model_id="mock-strong",
            provider="mock",
            spec_id="fizzbuzz",
            tier="easy",
            tags=["algorithms"],
            scores=DimensionScores(1.0, 1.0, 0.6, 0.5, semantic_judge="j", semantic_derived=True),
            composite=0.8,
        ),
        EvalResult(
            model_id="mock-weak",
            provider="mock",
            spec_id="fizzbuzz",
            tier="easy",
            tags=["algorithms"],
            scores=DimensionScores(0.5, 0.5, 0.5, 0.25, semantic_judge="j", semantic_derived=True),
            composite=0.5,
        ),
    ]
    metadata = RunMetadata(
        provider="mock",
        models=["mock-strong", "mock-weak"],
        judge_model="j",
        judge_design=judge_design,
        judge_agreement=agreement,
        reference_baseline=reference_baseline,
        weights=dict(config.DEFAULT_WEIGHTS),
        thresholds=dict(config.DEFAULT_THRESHOLDS),
        mock=False,
    )
    run = RunResults(metadata=metadata, results=results)
    if schema_version is not None:
        run.schema_version = schema_version
    return run


def test_agreement_figure_is_recorded_in_saved_results(tmp_path):
    agreement = {"judges": ["a", "b"], "n": 20, "exact_match_rate": 0.9, "mean_absolute_difference": 0.05}
    path = tmp_path / "results.json"
    reporting.save_results(_run(agreement=agreement), path)
    payload = json.loads(path.read_text())
    assert payload["metadata"]["judge_agreement"]["exact_match_rate"] == 0.9


def test_report_renders_the_agreement_figure_when_known():
    agreement = {"judges": ["a", "b"], "n": 20, "exact_match_rate": 0.9, "mean_absolute_difference": 0.05}
    report = reporting.render_report(_run(agreement=agreement))
    assert "90%" in report
    assert "0.050" in report


def test_report_states_agreement_unmeasured_when_unknown():
    report = reporting.render_report(_run())
    assert "Judge agreement has not been measured" in report


def test_report_states_stability_not_correctness():
    agreement = {"judges": ["a", "b"], "n": 20, "exact_match_rate": 0.9, "mean_absolute_difference": 0.05}
    report = reporting.render_report(_run(agreement=agreement))
    assert "stability, not correctness" in report
    assert "share a bias" in report


# --- 4.1 - 4.4 reporting the opinion and the history ------------------------


def test_report_separates_semantic_from_the_composite():
    report = reporting.render_report(_run())
    assert "semantic" in report
    assert "excluded from it" in report
    assert "not** in the composite" in report


def test_report_states_what_the_composite_excludes():
    report = reporting.render_report(_run())
    assert "does not say" in report
    assert "does it do what was asked" in report


def test_historical_results_are_marked_as_the_previous_judge_design():
    report = reporting.render_report(_run(schema_version=2, judge_design=None))
    assert "Historical result" in report
    assert "blended into the composite" in report


def test_current_results_are_not_marked_historical():
    report = reporting.render_report(_run(judge_design=config.JUDGE_DESIGN))
    assert "Historical result" not in report


# --- 5.1 - 5.3 reference baseline row ---------------------------------------


def test_reference_baseline_row_renders_when_recorded():
    baseline = {"execution": 1.0, "edge": 1.0, "style": 0.6, "specs": {"fizzbuzz": {}}}
    report = reporting.render_report(_run(reference_baseline=baseline))
    assert "## Reference baseline" in report
    assert "`reference`" in report


def test_reference_scores_one_on_execution_and_edge_and_records_style():
    specs = corpus.load_corpus(CORPUS_ROOT)
    baseline = pipeline.reference_baseline(specs, suite_timeout_s=60.0)
    assert len(baseline["specs"]) == 20
    assert all(row["execution"] == 1.0 for row in baseline["specs"].values())
    assert all(row["edge"] == 1.0 for row in baseline["specs"].values())
    # Style is a heuristic, not a verdict. A reference below 1.0 is a fact about
    # the style dimension, not a broken reference.
    assert baseline["style"] < 1.0
