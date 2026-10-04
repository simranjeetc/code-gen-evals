"""Score aggregation by model, tier, and task type, plus the guards.

Two guards are defined here alongside the aggregates: the degenerate guard (every
model scored identically, so the corpus measured nothing) and the exclusion-rate
guard (too many attempts were not measurements). The variance guard lives here
too, because it is the same shape of judgement over the same aggregates: a model
whose own score is not repeatable cannot be ranked against another.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..models import DIMENSIONS, OBJECTIVE_DIMENSIONS, OUTCOME_SCORED

DIMS = DIMENSIONS

# Reported in place of a spread when fewer than two scored repeats exist. A
# spread of 0.00 would look like evidence of stability; it is absence of
# evidence, and the same defect class as a failure scored as zero.
SPREAD_NOT_MEASURED = "not_measured"

# The smallest composite difference treated as a material separation between a
# control model and the subjects. A control must be a visible step below the
# pack, not merely below its mean; without this floor, perfectly stable subjects
# (sd = 0) would make any trivial gap look like discrimination.
MATERIAL_GAP = 0.05


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


def _population_sd(values: Sequence[float]) -> Optional[float]:
    """Population standard deviation, or ``None`` for fewer than two values.

    Population (not sample) because the repeats that ran *are* the observations
    in hand; there is no larger population being estimated. Returning ``None``
    below two values is deliberate: a single repeat has no measurable spread, and
    reporting ``0.0`` would claim stability that was never observed.
    """
    present = [float(value) for value in values if value is not None]
    if len(present) < 2:
        return None
    mean = sum(present) / float(len(present))
    variance = sum((value - mean) ** 2 for value in present) / float(len(present))
    return math.sqrt(variance)


def spread(values: Sequence[Optional[float]]) -> Dict[str, Any]:
    """Mean, min, max and standard deviation of a sequence of measurements.

    ``sd`` and the min/max range are ``None`` (rendered as ``not_measured``) when
    fewer than two values are present: repetition is what makes a spread
    meaningful, and one sample has none.
    """
    present = [float(value) for value in values if value is not None]
    if not present:
        return {
            "n": 0,
            "mean": None,
            "min": None,
            "max": None,
            "sd": None,
            "range": None,
            "measured": False,
        }
    measured = len(present) >= 2
    return {
        "n": len(present),
        "mean": sum(present) / float(len(present)),
        "min": min(present),
        "max": max(present),
        "sd": _population_sd(present),
        "range": (max(present) - min(present)) if measured else None,
        "measured": measured,
    }


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


def _pair_stability(
    group: Sequence[Any], weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """Repeat stability of one ``(model, spec)`` pair.

    A spread is only meaningful *within* a pair: pooling different specs would
    measure how different the specs are, not how repeatable the model is. This
    groups the scored attempts of a single pair by repeat and takes the spread of
    their composites.

    ``weights`` is used only to compute a composite when one is missing, so the
    guard works on freshly built results rather than depending on a prior
    :func:`aggregate` call having populated them.
    """
    scored = [result for result in group if is_scored(result)]
    composites = []
    for result in scored:
        value = getattr(result, "composite", None)
        if value is None and weights is not None:
            value = composite(result.scores, weights)
        composites.append(value)
    return {
        "composite": spread(composites),
        "dimensions": {
            dimension: spread([getattr(result.scores, dimension, None) for result in scored])
            for dimension in DIMS
        },
    }


def _aggregate_stability(pairs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarise per-pair spreads into a model-level stability block.

    Every figure is a **within-pair** quantity: pooling different specs would
    report how different the specs are, not how repeatable the model is. ``sd`` is
    the mean per-pair standard deviation — the noise a cross-model gap must clear
    — and ``spec_sd`` is the widest single-spec sd, so a model that is stable on
    average but wild on one spec is still visible. Cross-spec spread is deliberately
    not reported here; that is what the composite columns are for.
    """
    measured = [pair["composite"] for pair in pairs if pair["composite"].get("measured")]
    composites = [
        pair["composite"]["mean"]
        for pair in pairs
        if pair["composite"].get("mean") is not None
    ]
    if not measured:
        return {
            "n_pairs": len(pairs),
            "pairs_measured": 0,
            "mean": _mean(composites),
            "sd": None,
            "spec_sd": None,
            "range": None,
            "measured": False,
        }
    sds = [row["sd"] for row in measured]
    return {
        "n_pairs": len(pairs),
        "pairs_measured": len(measured),
        "mean": _mean(composites),
        "sd": sum(sds) / float(len(sds)),
        "spec_sd": max(sds),
        "range": _mean([row["range"] for row in measured]),
        # Always True here: a spread exists if at least one pair had repeats.
        "measured": True,
    }


def _dimension_stability(pairs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for dimension in DIMS:
        sds = [
            pair["dimensions"][dimension]["sd"]
            for pair in pairs
            if pair["dimensions"][dimension].get("measured")
        ]
        out[dimension] = {
            "sd": (sum(sds) / float(len(sds))) if sds else None,
            "measured": bool(sds),
        }
    return out


def aggregate(results: Sequence[Any], weights: Dict[str, float]) -> Dict[str, Any]:
    """Aggregate a run into everything the report needs.

    Averages are computed over **scored attempts only**. Infrastructure
    failures never contribute a zero; they are counted and reported alongside
    every aggregate through ``_exclusion_stats``.

    Repeat stability is computed **per ``(model, spec)`` pair** and then summarised
    across pairs. Pooling repeats across different specs would report how different
    the specs are, not how repeatable the model is, and would make a single-repeat
    run look wildly unstable.
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
        pairs = [_pair_stability(pair) for pair in _group(scored, lambda r: r.spec_id).values()]
        summary["stability"] = _aggregate_stability(pairs)
        summary["dimension_spread"] = _dimension_stability(pairs)
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
        "by_spec_model": _by_spec_model(results),
        "ranking": ranking,
    }


def _by_spec_model(results: Sequence[Any]) -> Dict[str, Dict[str, Any]]:
    """Per ``(spec, model)`` repeat stability, so an unstable spec is visible.

    An aggregate hides a spec that swings wildly between repeats behind its mean;
    this exposes the swing. Only scored attempts contribute.
    """
    grouped: Dict[Any, List[Any]] = {}
    for result in results:
        if not is_scored(result):
            continue
        grouped.setdefault((result.spec_id, result.model_id), []).append(result)

    rows: Dict[str, Dict[str, Any]] = {}
    for (spec_id, model_id), group in grouped.items():
        row = spread([result.composite for result in group])
        row["spec_id"] = spec_id
        row["model_id"] = model_id
        row["tier"] = group[0].tier
        rows.setdefault(spec_id, {})[model_id] = row
    return rows


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


def variance_reason(
    results: Sequence[Any],
    threshold: float,
    multiplier: float = 2.0,
    weights: Optional[Dict[str, float]] = None,
) -> Tuple[Optional[str], List[str]]:
    """Name models whose own composite is not repeatable.

    Distinct from :func:`degenerate_reason` (models not differentiating) and
    :func:`unreliable_reason` (attempts that were not measurements): this says a
    model's number moves too much run-to-run for its gap to another model to be
    read. The threshold and the interpretation rule are stated in the reason so
    the judgement is recorded with the run.
    """
    results = list(results)
    if not results:
        return None, []

    flagged: List[Tuple[str, float]] = []
    for model_id, group in _group(results, lambda r: r.model_id).items():
        scored = [result for result in group if is_scored(result)]
        pairs = [
            _pair_stability(pair, weights)
            for pair in _group(scored, lambda r: r.spec_id).values()
        ]
        stability = _aggregate_stability(pairs)
        sd = stability.get("sd")
        if sd is not None and sd > threshold:
            flagged.append((model_id, sd))
    if not flagged:
        return None, []

    flagged.sort(key=lambda item: item[1], reverse=True)
    names = [model_id for model_id, _ in flagged]
    worst = flagged[0][1]
    hurdle = multiplier * worst
    detail = ", ".join(f"`{model_id}` (sd={sd:.3f})" for model_id, sd in flagged)
    rule = (
        f"composite standard deviation exceeds the {threshold:.3f} threshold for "
        f"{detail}; a gap smaller than approximately {multiplier:g}x sd "
        f"(here {hurdle:.3f}) is not distinguishable from run-to-run noise"
    )
    return rule, names


def control_reason(
    by_model: Dict[str, Any], control_model: Optional[str], multiplier: float = 2.0
) -> Tuple[Optional[bool], Optional[str]]:
    """Did the corpus separate the deliberately weak control from the subjects?

    Returns ``(separated, reason)``. ``separated`` is ``None`` when no control is
    present or its spread could not be measured — the report must then say the
    corpus's ability to discriminate was not measured, rather than stay silent.
    """
    if not control_model:
        return None, (
            "no control model was present, so the corpus's ability to "
            "discriminate was not measured"
        )
    control = by_model.get(control_model)
    if control is None or control.get("composite") is None:
        return None, (
            f"the control model `{control_model}` produced no scored attempts, so "
            "the corpus's ability to discriminate was not measured"
        )

    peers = [
        stats for model_id, stats in by_model.items()
        if model_id != control_model and stats.get("composite") is not None
    ]
    if not peers:
        return None, (
            "the control model was the only model scored, so there was nothing "
            "for the corpus to separate it from"
        )

    peer_mean = sum(stats["composite"] for stats in peers) / float(len(peers))
    gap = peer_mean - control["composite"]

    # Two floors, both must be cleared. The noise floor is the widest subject sd,
    # doubled. The material floor is the peer composite range: with subjects
    # that are perfectly stable the noise floor is 0, and without a second floor
    # any trivial gap would count as separation. When peers are identical their
    # range is 0, so a small step stands in — a control must be a visible step
    # below the pack, not merely below its mean.
    peer_composites = [stats["composite"] for stats in peers]
    peer_range = (max(peer_composites) - min(peer_composites)) if len(peer_composites) > 1 else 0.0
    sds = [
        stats.get("stability", {}).get("sd")
        for stats in peers
        if stats.get("stability", {}).get("sd") is not None
    ]
    noise = (max(sds) * multiplier) if sds else 0.0
    material = max(peer_range, MATERIAL_GAP)

    floor = max(noise, material)
    separated = gap > floor
    components = []
    if noise > 0:
        components.append(f"noise floor {noise:.3f} ({multiplier:g}x widest subject sd)")
    components.append(f"material floor {material:.3f}")
    floor_text = " and ".join(components)
    direction = "below" if gap > 0 else "at or above"
    comparison = (
        f"the control's gap of {gap:.3f} {direction} the subjects' mean exceeds the "
        f"{floor_text}"
        if separated
        else f"the control's gap of {gap:.3f} {direction} the subjects' mean is "
        f"within the {floor_text}"
    )

    if separated:
        reason = (
            f"the corpus separated the control `{control_model}` "
            f"({control['composite']:.3f}) from the subjects (mean {peer_mean:.3f}): "
            f"{comparison}. The corpus discriminates, and a narrow spread among the "
            "remaining models is a property of the bank rather than the corpus."
        )
    else:
        reason = (
            f"the corpus did not separate the control `{control_model}` "
            f"({control['composite']:.3f}) from the subjects (mean {peer_mean:.3f}): "
            f"{comparison}. The corpus cannot discriminate, so the model bank is not "
            "the limiting factor."
        )
    return separated, reason


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
