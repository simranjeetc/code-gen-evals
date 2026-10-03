"""Score aggregation by model, tier, and task type, plus the degenerate guard."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..models import DIMENSIONS

DIMS = DIMENSIONS


def composite(scores, weights: Dict[str, float]) -> Optional[float]:
    """Weighted composite over the dimensions that are present.

    Weights are renormalised over available dimensions, so a judge abstention
    removes semantic from the average instead of counting it as zero.
    """
    total = 0.0
    used = 0.0
    for dimension, weight in weights.items():
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
    """Aggregate a run into everything the report needs."""
    results = list(results)

    for result in results:
        result.composite = composite(result.scores, weights)

    by_model: Dict[str, Any] = {}
    for model_id, group in _group(results, lambda r: r.model_id).items():
        summary = _dimension_summary([r.scores for r in group])
        summary["composite"] = _mean([r.composite for r in group])
        summary["composites"] = {
            r.spec_id: r.composite for r in group
        }
        by_model[model_id] = summary

    by_tier: Dict[str, Dict[str, Any]] = {}
    for model_id in by_model:
        by_tier[model_id] = {}
        model_results = [r for r in results if r.model_id == model_id]
        for tier, group in _group(model_results, lambda r: r.tier).items():
            summary = _dimension_summary([r.scores for r in group])
            summary["composite"] = _mean([r.composite for r in group])
            by_tier[model_id][tier] = summary

    by_task_type: Dict[str, Dict[str, Any]] = {}
    for model_id in by_model:
        by_task_type[model_id] = {}
        model_results = [r for r in results if r.model_id == model_id]
        buckets: Dict[str, List[Any]] = {}
        for result in model_results:
            for tag in result.tags or ["untagged"]:
                buckets.setdefault(tag, []).append(result)
        for tag, group in buckets.items():
            summary = _dimension_summary([r.scores for r in group])
            summary["composite"] = _mean([r.composite for r in group])
            by_task_type[model_id][tag] = summary

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


def _signature(scores) -> tuple:
    return (
        scores.execution,
        scores.edge,
        scores.style,
        -1.0 if scores.semantic is None else scores.semantic,
    )


def degenerate_reason(results: Sequence[Any]) -> Optional[str]:
    """Why a run fails to differentiate models, or ``None`` if it is fine."""
    results = list(results)
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
