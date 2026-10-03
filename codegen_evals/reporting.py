"""Markdown report rendering from persisted results.

The report is a pure function of a results file: it needs no network, no models,
and no re-run. That makes it cheap to re-render after changing weights or
thresholds, and it means a report can be reproduced from the artifact alone.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from . import config
from .models import (
    DIMENSIONS,
    OUTCOME_SCORED,
    SCHEMA_VERSION,
    TIERS,
    RunMetadata,
    RunResults,
)
from .scoring import aggregate, disagreements


def save_results(run: RunResults, path) -> None:
    """Write a results artifact, creating parent directories as needed.

    The file carries a derived ``summary`` block so the exclusion counts behind
    every average are present in the artifact, not only in the rendered report.
    It is a pure function of the raw results and the recorded weights.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    weights = run.metadata.weights or dict(config.DEFAULT_WEIGHTS)
    summary = aggregate.aggregate(run.results, weights)
    payload = run.to_dict()
    payload["metadata"]["schema_name"] = config.RESULTS_SCHEMA_NAME
    payload["summary"] = summary
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def load_results(path) -> RunResults:
    """Read a results artifact back into :class:`RunResults`."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return RunResults.from_dict(data)


def _fmt(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> List[str]:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def _metadata_section(run: RunResults) -> List[str]:
    meta = run.metadata
    lines = ["## Run metadata", ""]
    lines.append(f"- **schema version:** {run.schema_version}")
    lines.append(f"- **provider:** `{meta.provider}`")
    lines.append(f"- **models:** " + ", ".join(f"`{m}`" for m in meta.models) if meta.models else "- **models:** —")
    if meta.judge_model:
        lines.append(f"- **semantic judge:** `{meta.judge_model}`")
    lines.append(f"- **corpus:** {meta.corpus_count} specs")
    if meta.tier_counts:
        tiers = ", ".join(f"{tier}={meta.tier_counts.get(tier, 0)}" for tier in TIERS)
        lines.append(f"- **tier counts:** {tiers}")
    lines.append(f"- **temperature:** {meta.temperature}")
    lines.append(f"- **composite weights:** {meta.weights}")
    lines.append(f"- **disagreement thresholds:** {meta.thresholds}")
    if meta.timeout_s is not None:
        lines.append(f"- **provider timeout:** {meta.timeout_s:g}s (transient failures retried once)")
    if meta.exclusion_rate_threshold is not None:
        lines.append(
            f"- **exclusion-rate threshold:** {meta.exclusion_rate_threshold:.0%}"
        )
    lines.append(f"- **started:** {meta.started_at or '—'}")
    lines.append(f"- **finished:** {meta.finished_at or '—'}")
    lines.append(f"- **duration:** {_fmt(meta.duration_s, 1)}s")
    if run.schema_version < SCHEMA_VERSION:
        lines.append("")
        lines.append(
            f"> **Stale schema.** This file is schema version {run.schema_version}; "
            f"current is {SCHEMA_VERSION}. Earlier files scored infrastructure "
            "failures as `0.0`, so their numbers are not comparable with new runs."
        )
    if meta.mock:
        lines.append("")
        lines.append(
            "> **Mock run.** The `mock` provider synthesises candidates from the "
            "reference solutions. This validates the pipeline; it is not a "
            "comparison of real models."
        )
    if meta.inconclusive:
        lines.append("")
        lines.append(f"> **INCONCLUSIVE RUN.** {meta.inconclusive_reason}")
    lines.append("")
    return lines


def _methodology_section() -> List[str]:
    lines: List[str] = [
        "## Method",
        "",
        "Every model is scored on four independent dimensions for every spec, "
        "each in `[0.0, 1.0]`:",
        "",
    ]
    lines.extend(
        _table(
            ["Dimension", "What it measures", "Source"],
            [
                ["execution", "passes the hidden ground-truth pytest suite", "fraction of tests passed"],
                ["edge", "survives inputs the model never saw", "fraction of hidden edge tests passed"],
                ["semantic", "does what was actually asked", "independent judge model, fixed rubric"],
                ["style", "idiomatic, typed, readable Python", "deterministic static checks"],
            ],
        )
    )
    lines.extend(
        [
            "",
            "Composite = weighted mean over available dimensions (defaults: "
            "execution 0.4, edge 0.25, semantic 0.25, style 0.1), renormalised when a "
            "dimension is unavailable.",
            "",
            "### Attempt outcomes",
            "",
            "Every attempt is classified (`scored`, `timeout`, `provider_error`, "
            "`unparseable_output`, `not_attempted`). Only **scored** attempts — code "
            "was produced and run, whether or not it passed — are averaged. A "
            "provider timeout or crash is an infrastructure failure: it is counted "
            "and listed under Reliability, never scored as `0.0`. A crash inside the "
            "sandbox is **scored**, because the harness worked and the model's code "
            "did not. `timeout` and `provider_error` are retried once at a longer "
            "budget; `unparseable_output` is not. These are separate from a "
            "**semantic abstention** (no judge was available or its reply was "
            "unparseable), which is also excluded but for a different reason.",
            "",
            "### Limitations of each method",
            "",
            "- **execution** — the tests only assert what they assert. A green score "
            "means \"passed the cases we wrote\", not \"correct\".",
            "- **edge** — the edge suite is finite and hidden. It raises the bar over "
            "the visible suite; it does not bound correctness.",
            "- **semantic** — an LLM judge. Self-preference is blocked by requiring a "
            "different judge model, but verbosity bias, position sensitivity, and "
            "run-to-run drift are not eliminated. Rationales are recorded so calls can "
            "be audited.",
            "- **style** — heuristics, not taste. Annotations and docstrings are "
            "rewarded outright; terse-but-clear code is penalised.",
            "- **corpus** — 20 specs is a small sample, and these are well-known tasks, "
            "so training-data contamination is not controlled for. Read per-spec "
            "results before trusting a small gap.",
            "",
        ]
    )
    return lines


def _ranking_section(summary: Dict[str, Any]) -> List[str]:
    lines = ["## Model comparison", ""]
    lines.append("All four dimensions plus the composite, best composite first.")
    lines.append("")
    lines.append(
        "`n` is the number of scored attempts each average is based on; `excl` "
        "counts attempts excluded as infrastructure failures (see Reliability)."
    )
    lines.append("")
    headers = ["Model", "Composite"] + [dim for dim in DIMENSIONS] + ["n", "excl"]
    rows: List[List[str]] = []
    for row in summary["ranking"]:
        model_id = row["model_id"]
        stats = summary["by_model"][model_id]
        rows.append(_ranking_row(model_id, stats, bold=True))
    for model_id, stats in summary["by_model"].items():
        if any(row[0] == f"`{model_id}`" for row in rows):
            continue
        rows.append(_ranking_row(model_id, stats, bold=False))
    lines.extend(_table(headers, rows))
    lines.append("")
    return lines


def _ranking_row(model_id: str, stats: Dict[str, Any], bold: bool) -> List[str]:
    composite = _fmt(stats["composite"])
    if bold:
        composite = f"**{composite}**"
    return (
        [f"`{model_id}`", composite]
        + [_fmt(stats.get(dim)) for dim in DIMENSIONS]
        + [str(stats["n"]), str(stats.get("excluded", 0))]
    )


def _tier_section(summary: Dict[str, Any]) -> List[str]:
    lines = ["## Performance by difficulty tier", ""]
    headers = [
        "Model",
        "Tier",
        "Composite",
        "execution",
        "edge",
        "semantic",
        "style",
        "n",
        "excl",
    ]
    rows: List[List[str]] = []
    for model_id, tiers in summary["by_tier"].items():
        for tier in TIERS:
            stats = tiers.get(tier)
            if not stats:
                continue
            rows.append(
                [f"`{model_id}`", tier, f"**{_fmt(stats['composite'])}**"]
                + [_fmt(stats.get(dim)) for dim in DIMENSIONS]
                + [str(stats["n"]), str(stats.get("excluded", 0))]
            )
    if not rows:
        lines.append("_No results._")
    else:
        lines.extend(_table(headers, rows))
    lines.append("")
    return lines


def _task_type_section(summary: Dict[str, Any]) -> List[str]:
    lines = ["## Strengths and weaknesses by task type", ""]
    any_rows = False
    for model_id in summary["by_model"]:
        buckets = summary["by_task_type"].get(model_id) or {}
        if not buckets:
            continue
        any_rows = True
        lines.append(f"### `{model_id}`")
        lines.append("")
        rows = [
            [tag, _fmt(stats["composite"]), str(stats["n"]), str(stats.get("excluded", 0))]
            for tag, stats in sorted(
                buckets.items(),
                key=lambda item: (item[1]["composite"] is None, -(item[1]["composite"] or 0.0)),
            )
        ]
        lines.extend(_table(["Task type", "Composite", "n", "excl"], rows))
        best, worst = aggregate.task_type_extremes(summary["by_task_type"], model_id)
        lines.append("")
        if best and worst:
            lines.append(
                f"- **Strongest:** `{best[0]}` ({_fmt(best[1])}) — "
                f"**Weakest:** `{worst[0]}` ({_fmt(worst[1])})"
            )
        lines.append("")
        lines.append(
            "_Task-type buckets often hold one or two specs; treat a single-bucket "
            "difference as noise, not a finding._"
        )
        lines.append("")
    if not any_rows:
        lines.append("_No task-type tags available._")
        lines.append("")
    return lines


def _disagreement_section(run: RunResults, thresholds: Dict[str, float]) -> List[str]:
    lines = ["## Disagreements", ""]
    items = [
        (result, item)
        for result in run.results
        for item in (result.disagreements or [])
    ]
    if not items:
        lines.append("No cross-dimension disagreements were flagged for these thresholds.")
        lines.append("")
        return lines

    counts = disagreements.summarise([item for _, item in items])
    lines.append(
        "Cases where the dimensions disagree — the reason four scores are reported "
        "instead of one. Thresholds: "
        f"high ≥ {thresholds.get('high')}, low < {thresholds.get('low')}."
    )
    lines.append("")
    lines.extend(
        _table(
            ["Kind", "Count"],
            [[f"`{kind}`", str(count)] for kind, count in sorted(counts.items())],
        )
    )
    lines.append("")
    for result, item in items:
        lines.append(f"### `{result.model_id}` × `{result.spec_id}` — `{item.kind}`")
        lines.append("")
        lines.append(f"- **dimensions:** {', '.join(item.dimensions)}")
        lines.append(f"- **what happened:** {item.detail}")
        evidence = item.evidence or {}
        scalar = {k: v for k, v in evidence.items() if not isinstance(v, dict)}
        if scalar:
            lines.append(
                "- **evidence:** " + ", ".join(f"{k}={_fmt(v)}" for k, v in scalar.items())
            )
        failing = evidence.get("failing_checks")
        if failing:
            lines.append(f"- **failing style checks:** {failing}")
        lines.append("")
    return lines


def _reliability_section(run: RunResults) -> List[str]:
    lines = ["## Reliability", ""]
    meta = run.metadata
    failures = [
        result
        for result in run.results
        if getattr(result, "outcome", OUTCOME_SCORED) != OUTCOME_SCORED
    ]

    if meta.unreliable:
        names = ", ".join(f"`{name}`" for name in meta.unreliable_models) or "unknown"
        lines.append(
            f"> **UNRELIABLE RUN.** {meta.unreliable_reason}. The scores below are "
            f"computed over scored attempts only, but for {names} too few attempts "
            "were measurements for their numbers to be trusted."
        )
        lines.append("")

    if not failures:
        lines.append(
            "No infrastructure failures were recorded; every attempt was scored."
        )
        lines.append("")
        return lines

    lines.append(
        f"{len(failures)} of {len(run.results)} attempts were infrastructure "
        "failures and are excluded from every average in this report. They are "
        "listed here rather than shown as low model scores."
    )
    lines.append("")

    by_model: Dict[str, Dict[str, int]] = {}
    for result in run.results:
        stats = by_model.setdefault(result.model_id, {"attempts": 0, "excluded": 0})
        stats["attempts"] += 1
        if getattr(result, "outcome", OUTCOME_SCORED) != OUTCOME_SCORED:
            stats["excluded"] += 1

    rate_rows = []
    for model_id, stats in by_model.items():
        rate = stats["excluded"] / float(stats["attempts"]) if stats["attempts"] else 0.0
        rate_rows.append(
            [
                f"`{model_id}`",
                str(stats["attempts"]),
                str(stats["attempts"] - stats["excluded"]),
                str(stats["excluded"]),
                f"{rate:.0%}",
            ]
        )
    lines.extend(_table(["Model", "attempts", "scored", "excluded", "rate"], rate_rows))
    lines.append("")

    fail_rows = []
    for result in sorted(failures, key=lambda r: (r.model_id, r.spec_id)):
        attempts = 1 + int(result.retry_count or 0)
        message = (result.generation_error or "").replace("\n", " ")[:160]
        fail_rows.append(
            [
                f"`{result.model_id}`",
                result.spec_id,
                f"`{getattr(result, 'outcome', 'unknown')}`",
                str(attempts),
                message or "—",
            ]
        )
    lines.extend(_table(["Model", "Spec", "Outcome", "Attempts", "Message"], fail_rows))
    lines.append("")
    lines.append(
        "_An infrastructure failure means the model was not fairly tested. A "
        "timeout or provider error is retried once at a longer budget before being "
        "recorded here._"
    )
    lines.append("")
    return lines


def _per_spec_section(run: RunResults) -> List[str]:
    lines = ["## Per-spec results", ""]
    lines.append(
        "Aggregates hide single-spec differences; this is the raw table. With 20 "
        "specs, a gap under ~0.15 on one spec is not meaningfully different."
    )
    lines.append("")
    headers = ["Spec", "Tier", "Model", "Composite", "execution", "edge", "semantic", "style", "flags"]
    rows: List[List[str]] = []
    for result in sorted(run.results, key=lambda r: (r.spec_id, r.model_id)):
        outcome = getattr(result, "outcome", OUTCOME_SCORED)
        if outcome != OUTCOME_SCORED:
            # An infrastructure failure is not a low score. It is shown as
            # excluded, with its outcome, and detailed under Reliability.
            rows.append(
                [
                    result.spec_id,
                    result.tier,
                    f"`{result.model_id}`",
                    f"_excluded ({outcome})_",
                    "—",
                    "—",
                    "—",
                    "—",
                    outcome,
                ]
            )
            continue
        flags = ",".join(sorted({item.kind for item in (result.disagreements or [])})) or ""
        rows.append(
            [
                result.spec_id,
                result.tier,
                f"`{result.model_id}`",
                _fmt(result.composite),
                _fmt(result.scores.execution),
                _fmt(result.scores.edge),
                _fmt(result.scores.semantic),
                _fmt(result.scores.style),
                flags,
            ]
        )
    if rows:
        lines.extend(_table(headers, rows))
    else:
        lines.append("_No results._")
    lines.append("")
    return lines


def render_report(run: RunResults, weights: Optional[Dict[str, float]] = None) -> str:
    """Render the full Markdown report."""
    weights = weights or run.metadata.weights or dict(config.DEFAULT_WEIGHTS)
    thresholds = run.metadata.thresholds or dict(config.DEFAULT_THRESHOLDS)
    summary = aggregate.aggregate(run.results, weights)

    lines: List[str] = ["# Code-generation model evaluation", ""]
    if run.metadata.inconclusive:
        lines.append(
            "> **This run is inconclusive.** "
            f"{run.metadata.inconclusive_reason} The corpus did not differentiate "
            "the models, so no ranking is meaningful."
        )
        lines.append("")
    if run.metadata.unreliable:
        names = ", ".join(f"`{m}`" for m in run.metadata.unreliable_models) or "unknown"
        lines.append(
            "> **This run is unreliable.** "
            f"{run.metadata.unreliable_reason}. Affected: {names}. Scores are "
            "computed over scored attempts only, but too many attempts were not "
            "measurements for the ranking to be trusted."
        )
        lines.append("")

    lines.extend(_metadata_section(run))
    lines.extend(_methodology_section())
    lines.extend(_ranking_section(summary))
    lines.extend(_reliability_section(run))
    lines.extend(_tier_section(summary))
    lines.extend(_task_type_section(summary))
    lines.extend(_disagreement_section(run, thresholds))
    lines.extend(_per_spec_section(run))
    lines.extend(
        [
            "## Reading this report",
            "",
            "- Prefer the four dimensions over the composite; the composite is a "
            "convenience with arbitrary weights.",
            "- A disagreement is not a bug — it is the finding. A model that passes "
            "every test and scores low on semantic is the interesting result.",
            "- Check the per-spec table before believing a small composite gap.",
            "- Averages exclude infrastructure failures. Check the Reliability "
            "section before reading a low score as a weak model.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(run: RunResults, path, weights: Optional[Dict[str, float]] = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(run, weights=weights), encoding="utf-8")


def build_run_metadata(
    provider: str,
    models: Sequence[str],
    judge_model: Optional[str],
    specs: Sequence[Any],
    weights: Dict[str, float],
    thresholds: Dict[str, float],
    temperature: float,
    mock: bool,
    started_at: str,
    finished_at: str,
    duration_s: float,
    timeout_s: Optional[float] = None,
    exclusion_rate_threshold: Optional[float] = None,
) -> RunMetadata:
    """Assemble the metadata block a results file needs to be self-describing."""
    from . import corpus as corpus_module

    return RunMetadata(
        provider=provider,
        models=list(models),
        judge_model=judge_model,
        corpus_count=len(specs),
        tier_counts=corpus_module.tier_counts(specs),
        weights=dict(weights),
        thresholds=dict(thresholds),
        temperature=temperature,
        mock=mock,
        started_at=started_at,
        finished_at=finished_at,
        duration_s=duration_s,
        timeout_s=timeout_s,
        exclusion_rate_threshold=exclusion_rate_threshold,
    )
