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


def _history_note(run: RunResults) -> List[str]:
    """Flag a file produced under an earlier, incomparable design."""
    meta = run.metadata
    reasons: List[str] = []
    if run.schema_version < 2:
        reasons.append("infrastructure failures were scored `0.0`")
    if run.schema_version < 3:
        reasons.append(
            "the judge scored absolutely with nothing to anchor it and its opinion "
            "was blended into the composite at weight 0.25"
        )
    if run.schema_version < 4:
        reasons.append(
            "each (model, spec) pair was attempted once, so no score carried a "
            "measured repeat spread and a gap could not be compared against noise"
        )
    lines: List[str] = []
    if reasons:
        lines.append("")
        lines.append(
            f"> **Historical result.** This file is schema version "
            f"{run.schema_version} (current {SCHEMA_VERSION}). It was produced under "
            "a previous design where " + "; ".join(reasons) + ". Its numbers are not "
            "comparable with new runs."
        )
    elif meta.judge_model and not meta.judge_design:
        lines.append("")
        lines.append(
            "> **Historical judge design.** This file records no judge design; it "
            "predates reference-anchored judging. Treat its semantic scores as "
            "incomparable with new runs."
        )
    return lines


def _metadata_section(run: RunResults) -> List[str]:
    meta = run.metadata
    lines = ["## Run metadata", ""]
    lines.append(f"- **schema version:** {run.schema_version}")
    lines.append(f"- **provider:** `{meta.provider}`")
    lines.append(f"- **models:** " + ", ".join(f"`{m}`" for m in meta.models) if meta.models else "- **models:** —")
    if meta.judge_model:
        lines.append(f"- **semantic judge:** `{meta.judge_model}`")
    if meta.judge_design:
        lines.append(f"- **judge design:** {meta.judge_design}")
    if meta.judge_agreement:
        agreement = meta.judge_agreement
        rate = agreement.get("exact_match_rate")
        mad = agreement.get("mean_absolute_difference")
        lines.append(
            "- **judge agreement (stability):** "
            + (
                f"exact match {rate:.0%}, mean absolute difference {mad:.3f} "
                f"over {agreement.get('n', 0)} reference(s)"
                if rate is not None and mad is not None
                else "unmeasured"
            )
        )
    lines.append(f"- **corpus:** {meta.corpus_count} specs")
    if meta.tier_counts:
        tiers = ", ".join(f"{tier}={meta.tier_counts.get(tier, 0)}" for tier in TIERS)
        lines.append(f"- **tier counts:** {tiers}")
    lines.append(f"- **temperature:** {meta.temperature}")
    lines.append(f"- **repeats per pair:** {meta.repeat_count}")
    if meta.control_model:
        lines.append(f"- **control model:** `{meta.control_model}` (a control, never ranked as a peer)")
    if meta.variance_threshold is not None:
        multiplier = meta.instability_multiplier or 2.0
        lines.append(
            f"- **variance guard:** unstable when a model's composite sd exceeds "
            f"{meta.variance_threshold:.3f}; gaps under {multiplier:g}x sd are noise"
        )
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
    lines.extend(_history_note(run))
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
                ["semantic", "does what was actually asked", "reference-anchored judge model (an opinion, not a measurement)"],
                ["style", "idiomatic, typed, readable Python", "deterministic static checks"],
            ],
        )
    )
    lines.extend(
        [
            "",
            "**Composite** = weighted mean over the **objective** dimensions only "
            "(`execution` 0.5, `edge` 0.3, `style` 0.2), renormalised when one is "
            "unavailable. `semantic` is a judge's opinion and is **not** in the "
            "composite: an opinion blended into a measurement is the defect this "
            "design avoids. The composite therefore says \"does it work, survive, and "
            "read well\" — it does not say \"does it do what was asked\". Read the "
            "`semantic` column for that, and read it as an opinion.",
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


def _ranking_section(run: RunResults, summary: Dict[str, Any]) -> List[str]:
    lines = ["## Model comparison", ""]
    lines.append(
        "Best composite first. The composite covers `execution`, `edge` and `style` "
        "only; `semantic` is a judge's opinion shown alongside but excluded from it."
    )
    lines.append("")
    lines.append(
        "`n` is the number of scored attempts each average is based on; `excl` "
        "counts attempts excluded as infrastructure failures (see Reliability)."
    )
    lines.append("")
    headers = ["Model", "Composite"] + [dim for dim in DIMENSIONS] + ["n", "excl"]
    rows: List[List[str]] = []
    control_model = run.metadata.control_model
    for row in summary["ranking"]:
        model_id = row["model_id"]
        stats = summary["by_model"][model_id]
        rows.append(_ranking_row(model_id, stats, bold=True, control=(model_id == control_model)))
    for model_id, stats in summary["by_model"].items():
        if any(row[0].startswith(f"`{model_id}`") for row in rows):
            continue
        rows.append(_ranking_row(model_id, stats, bold=False, control=(model_id == control_model)))
    lines.extend(_table(headers, rows))
    lines.append("")
    lines.extend(_agreement_line(run))
    lines.append("")
    return lines


def _agreement_line(run: RunResults) -> List[str]:
    agreement = run.metadata.judge_agreement
    if not agreement or agreement.get("exact_match_rate") is None:
        return [
            "_Judge agreement has not been measured for this run, so how stable "
            "the `semantic` column is across judges is unknown._"
        ]
    rate = agreement["exact_match_rate"]
    mad = agreement.get("mean_absolute_difference")
    return [
        f"_`semantic` is judge-derived. Two judges agreed exactly on {rate:.0%} of "
        f"{agreement.get('n', 0)} reference solutions (mean absolute difference "
        f"{mad:.3f}). This measures **stability, not correctness** — two judges can "
        "share a bias and agree. Human agreement is not measured._"
    ]


def _ranking_row(model_id: str, stats: Dict[str, Any], bold: bool, control: bool = False) -> List[str]:
    composite = _fmt(stats["composite"])
    if bold:
        composite = f"**{composite}**"
    name = f"`{model_id}`"
    if control:
        name += " _(control)_"
    return (
        [name, composite]
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


def _stability_section(run: RunResults, summary: Dict[str, Any]) -> List[str]:
    """Repeat stability per model: the spread a composite gap must clear."""
    lines = ["## Repeat stability", ""]
    meta = run.metadata
    if meta.repeat_count <= 1:
        lines.append(
            "_Each pair was attempted once, so no repeat spread was measured. "
            "Run with `--repeats 2` or more to compare a gap against noise._"
        )
        lines.append("")
        return lines

    lines.append(
        f"Each `(model, spec)` pair was attempted **{meta.repeat_count}** times. The "
        "spread below is how much a model's own composite moves run-to-run — the "
        "noise a gap between models must clear to be reportable. It measures "
        "**repeatability, not eventual success**; it is not `pass@k`."
    )
    lines.append("")
    multiplier = meta.instability_multiplier or 2.0
    if meta.variance_threshold is not None:
        lines.append(
            f"Noise floor: a gap is treated as noise unless it exceeds "
            f"{multiplier:g}x a model's sd. The variance guard fires above an sd of "
            f"{meta.variance_threshold:.3f}."
        )
        lines.append("")

    headers = ["Model", "mean", "sd", "widest spec sd", "mean range", "specs"]
    rows: List[List[str]] = []
    for model_id, stats in summary["by_model"].items():
        stability = stats.get("stability") or {}
        name = f"`{model_id}`"
        if model_id == meta.control_model:
            name += " _(control)_"
        if stability.get("measured"):
            rows.append(
                [
                    name,
                    _fmt(stability["mean"]),
                    _fmt(stability["sd"], 3),
                    _fmt(stability["spec_sd"], 3),
                    _fmt(stability["range"], 3),
                    str(stability.get("pairs_measured", 0)),
                ]
            )
        else:
            rows.append(
                [
                    name,
                    _fmt(stability.get("mean")),
                    "not measured",
                    "—",
                    "—",
                    str(stability.get("n_pairs", 0)),
                ]
            )
    lines.extend(_table(headers, rows))
    lines.append("")
    lines.append(
        "`sd` is the mean per-spec standard deviation — the run-to-run noise. "
        "`widest spec sd` is the worst single spec, so a model stable on average "
        "but wild on one spec is still visible. Both are within-spec: they measure "
        "repeatability, not how much the model varies across different specs."
    )
    lines.append("")

    # Per-spec: expose a spec that swings between repeats.
    noisy = []
    for spec_id, by_model in (summary.get("by_spec_model") or {}).items():
        for model_id, row in by_model.items():
            if row.get("measured") and row.get("range") is not None and row["range"] >= 0.20:
                noisy.append((spec_id, model_id, row))
    if noisy:
        lines.append(
            "Specs whose composite swung by 0.20 or more across repeats (a candidate "
            "ambiguous or flaky spec, distinct from a genuinely hard one):"
        )
        lines.append("")
        noisy.sort(key=lambda item: item[2]["range"], reverse=True)
        lines.extend(
            _table(
                ["Spec", "Model", "mean", "sd", "range", "n"],
                [
                    [spec_id, f"`{model_id}`", _fmt(row["mean"]), _fmt(row["sd"], 3), _fmt(row["range"]), str(row["n"])]
                    for spec_id, model_id, row in noisy
                ],
            )
        )
        lines.append("")
    else:
        lines.append(
            "No spec's composite swung by 0.20 or more across repeats; variation is "
            "spread thinly rather than concentrated in one spec."
        )
        lines.append("")

    lines.append(
        "Dimension spreads show where the variation lives. The judge is the only "
        "non-deterministic axis, so `semantic` usually carries most of it; if the "
        "objective dimensions are far tighter than the composite, the composite's "
        "movement is the opinion, not the model."
    )
    lines.append("")
    dim_rows: List[List[str]] = []
    for model_id, stats in summary["by_model"].items():
        spreads = stats.get("dimension_spread") or {}
        name = f"`{model_id}`"
        if model_id == meta.control_model:
            name += " _(control)_"
        row = [name]
        for dimension in DIMENSIONS:
            value = (spreads.get(dimension) or {}).get("sd")
            row.append(_fmt(value, 3) if value is not None else "—")
        dim_rows.append(row)
    lines.extend(_table(["Model"] + [f"sd({dim})" for dim in DIMENSIONS], dim_rows))
    lines.append("")
    return lines


def _control_section(run: RunResults) -> List[str]:
    meta = run.metadata
    lines = ["## Control model (does the corpus discriminate?)", ""]
    if not meta.control_model:
        lines.append(
            "_No control model was present, so the corpus's ability to discriminate "
            "was not measured._"
        )
        lines.append("")
        return lines
    lines.append(
        f"A deliberately weak control, `{meta.control_model}`, is included so the "
        "corpus's ability to separate models is **measured** rather than assumed. "
        "The control is not a ranked peer."
    )
    lines.append("")
    if meta.control_reason:
        lines.append(meta.control_reason)
        lines.append("")
    if meta.control_separated is True:
        lines.append(
            "**Reading:** the corpus discriminates. A narrow spread among the "
            "remaining models is a property of the model bank, not the corpus; "
            "adding harder specs would not change that result."
        )
        lines.append("")
    elif meta.control_separated is False:
        lines.append(
            "**Reading:** the corpus did not separate a deliberately weak model from "
            "the subjects, so the corpus cannot discriminate at all. The model bank "
            "is not the limiting factor; harder specs are the fix."
        )
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

    if meta.unstable:
        names = ", ".join(f"`{name}`" for name in meta.unstable_models) or "unknown"
        lines.append(
            f"> **UNSTABLE RUN.** {meta.unstable_reason}. Affected: {names}. These "
            "models' own scores are not repeatable, so a gap between them and "
            "another model cannot be distinguished from run-to-run noise."
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


def _reference_baseline_section(run: RunResults) -> List[str]:
    baseline = run.metadata.reference_baseline
    lines = ["## Reference baseline", ""]
    if not baseline or not baseline.get("specs"):
        lines.append("_No reference baseline was recorded for this run._")
        lines.append("")
        return lines
    lines.append(
        "The task authors' accepted solutions scored on the objective dimensions — "
        "the ceiling the models are measured against. `semantic` is omitted: the "
        "reference *is* the standard, so judging it adds nothing."
    )
    lines.append("")
    rows = [
        [
            "`reference`",
            _fmt(baseline.get("execution")),
            _fmt(baseline.get("edge")),
            _fmt(baseline.get("style")),
            str(len(baseline["specs"])),
        ]
    ]
    lines.extend(_table(["Source", "execution", "edge", "style", "n"], rows))
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
    if run.metadata.unstable:
        names = ", ".join(f"`{m}`" for m in run.metadata.unstable_models) or "unknown"
        lines.append(
            "> **This run is unstable.** "
            f"{run.metadata.unstable_reason}. Affected: {names}. A model's own "
            "score is not repeatable, so its gap to another model cannot be read: "
            "do not report an ordering finer than the noise floor."
        )
        lines.append("")

    lines.extend(_metadata_section(run))
    lines.extend(_methodology_section())
    lines.extend(_ranking_section(run, summary))
    lines.extend(_stability_section(run, summary))
    lines.extend(_control_section(run))
    lines.extend(_reference_baseline_section(run))
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
    repeat_count: int = 1,
    control_model: Optional[str] = None,
    variance_threshold: Optional[float] = None,
    instability_multiplier: Optional[float] = None,
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
        repeat_count=repeat_count,
        control_model=control_model,
        variance_threshold=variance_threshold,
        instability_multiplier=instability_multiplier,
    )
