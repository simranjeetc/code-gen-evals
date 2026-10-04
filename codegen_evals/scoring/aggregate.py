"""Score aggregation by model, tier, and task type, plus the degenerate guard."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..models import DIMENSIONS, OBJECTIVE_DIMENSIONS, OUTCOME_SCORED

DIMS = DIMENSIONS


def is_scored(result: Any) -> bool:
    """True when an attempt is a measurement (not an infrastructure failure)."""
    return getattr(result, "outcome", OUTCOME_SCORED) == OUTCOME_SCORED


def _excluded(results: Sequence[Any]) -> List[Any]:
    return [result for result in results if not is_scored(result)]


def _exclusion_stats(results: Sequence[Any]) -> Dict[str, Any]:
    """Counts of non-scoring attempts, broken down by outcome."""
    excluded = _excluded(results)
    outcomes: Dict[str, int] = {}
    for result in excluded:
        outcome = getattr(result, "outcome", "unknown")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    attempts = len(results)
    return {
        "attempts": attempts,
        "excluded": len(excluded),
        "excluded_outcomes": outcomes,
        "exclusion_rate": (len(excluded) / float(attempts)) if attempts else 0.0,
    }


def composite(scores, weights: Dict[str, float]) -> Optional[float]:
    """Weighted composite over the **objective** dimensions that are present.

    ``semantic`` is a judge's opinion and is never blended in, even if a weight
    is supplied for it. Weights are renormalised over the available objective
    dimensions, so a missing measurement is excluded rather than counted as zero.
    """
    total = 0.0
    used = 0.0
    for dimension, weight in weights.items():
        if dimension not in OBJECTIVE_DIMENSIONS:
            continue
        value = getattr(scores, dimension, None)
        if value is None:
            continue
        total += float(weight) * float(value)
        used += float(weight)
    if used <= 0.0:
        return None
    return total / used


def _mean(values: Sequence[Optional[float]]) -> Optional[float]:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present) / float(len(present))


def _dimension_summary(scores_list: Sequence[Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for dimension in DIMS:
        summary[dimension] = _mean([getattr(scores, dimension, None) for scores in scores_list])
    summary["n"] = len(scores_list)
    semantic_present = sum(1 for s in scores_list if getattr(s, "semantic", None) is not None)
    summary["semantic_abstentions"] = len(scores_list) - semantic_present
    return summary


def _group(results: Iterable[Any], key):
    grouped: Dict[Any, List[Any]] = {}
    for result in results:
        grouped.setdefault(key(result), []).append(result)
    return grouped


def aggregate(results: Sequence[Any], weights: Dict[str, float]) -> Dict[str, Any]:
    """Aggregate a run into everything the report needs.

    Averages are computed over **scored attempts only**. Infrastructure
    failures never contribute a zero; they are counted and reported alongside
    every aggregate through ``_exclusion_stats``.
    """
    results = list(results)

    for result in results:
        if is_scored(result):
            result.composite = composite(result.scores, weights)
        else:
            result.composite = None

    def summarise(group: Sequence[Any]) -> Dict[str, Any]:
        scored = [result for result in group if is_scored(result)]
        summary = _dimension_summary([result.scores for result in scored])
        summary["composite"] = _mean([result.composite for result in scored])
        summary["composites"] = {result.spec_id: result.composite for result in scored}
        summary.update(_exclusion_stats(group))
        return summary

    by_model: Dict[str, Any] = {}
    for model_id, group in _group(results, lambda r: r.model_id).items():
        by_model[model_id] = summarise(group)

    by_tier: Dict[str, Dict[str, Any]] = {}
    for model_id in by_model:
        by_tier[model_id] = {}
        model_results = [r for r in results if r.model_id == model_id]
        for tier, group in _group(model_results, lambda r: r.tier).items():
            by_tier[model_id][tier] = summarise(group)

    by_task_type: Dict[str, Dict[str, Any]] = {}
    for model_id in by_model:
        by_task_type[model_id] = {}
        model_results = [r for r in results if r.model_id == model_id]
        buckets: Dict[str, List[Any]] = {}
        for result in model_results:
            for tag in result.tags or ["untagged"]:
                buckets.setdefault(tag, []).append(result)
        for tag, group in buckets.items():
            by_task_type[model_id][tag] = summarise(group)

    ranking = sorted(
        (
            {"model_id": model_id, "composite": summary["composite"]}
            for model_id, summary in by_model.items()
            if summary["composite"] is not None
        ),
        key=lambda row: row["composite"],
        reverse=True,
    )

    return {
        "weights": dict(weights),
        "by_model": by_model,
        "by_tier": by_tier,
        "by_task_type": by_task_type,
        "ranking": ranking,
    }


def unreliable_reason(
    results: Sequence[Any], threshold: float
) -> Tuple[Optional[str], List[str]]:
    """Name models whose infrastructure-failure rate exceeds ``threshold``.

    Distinct from :func:`degenerate_reason`: a run can be unreliable (too many
    attempts were not measurements) without being degenerate (models scoring
    identically), and vice versa.
    """
    results = list(results)
    if not results:
        return None, []

    flagged: List[Tuple[str, float]] = []
    for model_id, group in _group(results, lambda r: r.model_id).items():
        stats = _exclusion_stats(group)
        rate = stats["exclusion_rate"]
        if stats["excluded"] > 0 and rate > threshold:
            flagged.append((model_id, rate))

    if not flagged:
        return None, []

    flagged.sort(key=lambda item: item[1], reverse=True)
    names = [model_id for model_id, _ in flagged]
    detail = ", ".join(f"`{model_id}` ({rate:.0%})" for model_id, rate in flagged)
    return (
        f"infrastructure failures exceed the {threshold:.0%} threshold for {detail}",
        names,
    )


def _signature(scores) -> tuple:
    return (
        scores.execution,
        scores.edge,
        scores.style,
        -1.0 if scores.semantic is None else scores.semantic,
    )


def degenerate_reason(results: Sequence[Any]) -> Optional[str]:
    """Why a run fails to differentiate models, or ``None`` if it is fine.

    Only scored attempts are compared; an infrastructure failure is not a data
    point about a model.
    """
    results = [result for result in results if is_scored(result)]
    if not results:
        return "no results to compare"

    models = {result.model_id for result in results}
    if len(models) < 2:
        return None

    by_spec = _group(results, lambda r: r.spec_id)
    comparable = 0
    for group in by_spec.values():
        if len({result.model_id for result in group}) < 2:
            continue
        comparable += 1
        if len({_signature(result.scores) for result in group}) > 1:
            return None

    if comparable == 0:
        return "no spec was attempted by more than one model"

    signatures = {_signature(result.scores) for result in results}
    if signatures == {(1.0, 1.0, 1.0, 1.0)}:
        return "every model scored perfectly on every dimension for every spec"
    if signatures == {(0.0, 0.0, 0.0, 0.0)}:
        return "every model scored zero on every dimension for every spec"
    return "every model scored identically on every dimension for every spec"


def task_type_extremes(by_task_type: Dict[str, Any], model_id: str):
    """Best and worst task types for a model, ignoring single-spec noise."""
    buckets = {
        tag: summary["composite"]
        for tag, summary in (by_task_type.get(model_id) or {}).items()
        if summary["composite"] is not None
    }
    if not buckets:
        return None, None
    ordered = sorted(buckets.items(), key=lambda item: item[1])
    return ordered[-1], ordered[0]
