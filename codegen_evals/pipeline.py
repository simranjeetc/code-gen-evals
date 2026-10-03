"""End-to-end evaluation pipeline: corpus -> providers -> execution -> scoring.

Kept separate from ``cli.py`` so the orchestration can be driven
programmatically and tested without going through argument parsing.
"""

from __future__ import annotations

import datetime as _datetime
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Sequence

from . import config, corpus, execution, reporting
from .models import (
    DimensionScores,
    EvalResult,
    RunResults,
    Spec,
)
from .providers import ProviderConfigError, build_provider
from .scoring import aggregate, dimensions, disagreements, semantic, style


def _utc_now() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).isoformat()


def resolve_weights(weights: Optional[Dict[str, float]]) -> Dict[str, float]:
    resolved = dict(config.DEFAULT_WEIGHTS)
    for key, value in (weights or {}).items():
        if key not in config.DEFAULT_WEIGHTS:
            raise ValueError(
                f"unknown dimension '{key}' in weights; expected one of "
                f"{', '.join(config.DEFAULT_WEIGHTS)}"
            )
        resolved[key] = float(value)
    return resolved


def build_judge(
    provider_name: str,
    provider,
    judge_model: Optional[str],
    temperature: float = config.DEFAULT_TEMPERATURE,
    timeout_s: float = config.DEFAULT_TIMEOUT_S,
):
    """Pick a judge, or ``None`` when the caller did not configure one.

    Returning ``None`` means every semantic score abstains, which is honest:
    no judge was configured, so intent was not measured.
    """
    if provider_name == "mock":
        return semantic.MockJudge(provider.variant_for, judge_model or "mock-judge")
    if not judge_model:
        return None
    if provider_name == "opencode":
        judge_provider = build_provider(
            "opencode",
            agent=config.DEFAULT_JUDGE_AGENT,
            temperature=temperature,
            timeout_s=timeout_s,
        )
        return semantic.ProviderJudge(judge_provider, judge_model)
    if provider_name == "claude-code":
        judge_provider = build_provider(
            "claude-code",
            temperature=temperature,
            timeout_s=timeout_s,
        )
        return semantic.ProviderJudge(judge_provider, judge_model)
    return semantic.ProviderJudge(provider, judge_model)


def evaluate_pair(
    spec: Spec,
    model_id: str,
    provider,
    judge,
    weights: Dict[str, float],
    thresholds: Dict[str, float],
    python_executable: Optional[str] = None,
    suite_timeout_s: float = config.DEFAULT_SUITE_TIMEOUT_S,
    use_ruff: bool = False,
) -> EvalResult:
    """Evaluate one model against one spec.

    Never raises for a model-side failure: a bad generation becomes low scores.
    """
    prompt = corpus.render_prompt(spec)
    generation = provider.generate(prompt, model_id, spec_id=spec.id)

    ground_truth = None
    edge_case = None
    if generation.extracted and generation.code is not None:
        try:
            ground_truth, edge_case = execution.run_spec(
                spec,
                generation.code,
                timeout_s=suite_timeout_s,
                python_executable=python_executable,
            )
        except Exception as error:  # noqa: BLE001 - contained per pair
            ground_truth = execution.ExecutionEvidence(
                suite="ground_truth", setup_error=f"execution failed: {error}"
            )
            edge_case = execution.ExecutionEvidence(
                suite="edge_case", setup_error=f"execution failed: {error}"
            )

    execution_value = dimensions.execution_score(ground_truth, generation.extracted)
    edge_value = dimensions.edge_score(edge_case, generation.extracted)

    # Style is only meaningful for code that exists; no code scores zero.
    style_value, style_details = style.analyze_style(
        generation.code if generation.extracted else None, use_ruff=use_ruff
    )

    if judge is None:
        verdict = semantic.JudgeVerdict(error="no semantic judge was configured")
    else:
        verdict = judge.judge(spec, prompt, generation.code, model_id)

    scores = DimensionScores(
        execution=execution_value,
        edge=edge_value,
        style=style_value,
        semantic=verdict.score,
        semantic_rationale=verdict.rationale,
        semantic_judge=verdict.judge_model,
        style_checks=style_details.get("checks", {}),
    )

    result = EvalResult(
        model_id=model_id,
        provider=generation.provider,
        spec_id=spec.id,
        tier=spec.tier,
        tags=list(spec.tags),
        scores=scores,
        ground_truth=ground_truth,
        edge_case=edge_case,
        extraction_ok=generation.extracted,
        generation_duration_s=generation.duration_s,
        generation_error=generation.error,
    )
    result.composite = aggregate.composite(scores, weights)
    result.disagreements = disagreements.detect(scores, **thresholds)
    return result


def run_evaluation(
    specs: Sequence[Spec],
    models: Sequence[str],
    provider_name: str = "mock",
    judge_model: Optional[str] = None,
    weights: Optional[Dict[str, float]] = None,
    thresholds: Optional[Dict[str, float]] = None,
    temperature: float = config.DEFAULT_TEMPERATURE,
    concurrency: int = config.DEFAULT_CONCURRENCY,
    timeout_s: float = config.DEFAULT_TIMEOUT_S,
    suite_timeout_s: float = config.DEFAULT_SUITE_TIMEOUT_S,
    python_executable: Optional[str] = None,
    use_ruff: bool = False,
    progress: Optional[Callable[[str], None]] = None,
) -> RunResults:
    """Run the full pipeline and return a self-describing results object."""
    specs = list(specs)
    models = list(models)
    if not specs:
        raise ValueError("no specs selected")
    if not models:
        raise ValueError("no models selected")

    resolved_weights = resolve_weights(weights)
    resolved_thresholds = dict(config.DEFAULT_THRESHOLDS)
    resolved_thresholds.update(thresholds or {})

    if judge_model and judge_model in models:
        raise ProviderConfigError(
            f"judge model '{judge_model}' is also a subject; the judge must be a "
            "different model"
        )

    started_at = _utc_now()
    started = time.monotonic()

    provider = build_provider(
        provider_name, specs=specs, temperature=temperature, timeout_s=timeout_s
    )
    judge = build_judge(provider_name, provider, judge_model, temperature, timeout_s)

    pairs = [(spec, model_id) for model_id in models for spec in specs]
    if progress:
        progress(
            f"evaluating {len(models)} model(s) x {len(specs)} spec(s) "
            f"= {len(pairs)} pairs via '{provider_name}'"
            + (f", concurrency {concurrency}" if concurrency > 1 else "")
        )

    def work(pair):
        spec, model_id = pair
        return evaluate_pair(
            spec=spec,
            model_id=model_id,
            provider=provider,
            judge=judge,
            weights=resolved_weights,
            thresholds=resolved_thresholds,
            python_executable=python_executable,
            suite_timeout_s=suite_timeout_s,
            use_ruff=use_ruff,
        )

    if concurrency and concurrency > 1:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            results: List[EvalResult] = list(pool.map(work, pairs))
    else:
        results = [work(pair) for pair in pairs]

    results.sort(key=lambda result: (result.model_id, result.spec_id))

    finished_at = _utc_now()
    duration_s = time.monotonic() - started

    metadata = reporting.build_run_metadata(
        provider=provider_name,
        models=models,
        judge_model=(judge.judge_model if judge is not None else None),
        specs=specs,
        weights=resolved_weights,
        thresholds=resolved_thresholds,
        temperature=temperature,
        mock=(provider_name == "mock"),
        started_at=started_at,
        finished_at=finished_at,
        duration_s=duration_s,
    )

    run = RunResults(metadata=metadata, results=results)

    reason = aggregate.degenerate_reason(results)
    if reason is not None:
        run.metadata.inconclusive = True
        run.metadata.inconclusive_reason = reason
    if progress:
        progress(f"finished {len(results)} evaluations in {duration_s:.1f}s")

    return run
