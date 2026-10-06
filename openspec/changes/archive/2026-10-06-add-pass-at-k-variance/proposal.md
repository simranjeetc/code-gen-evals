# Proposal

## Why

Every reported number today is a **single sample**. A model's composite is the mean over 20 specs, each generated once. Nothing measures whether that number is repeatable, so nothing can say whether a gap between two models is real or luck.

This already matters, concretely. The current four-model run reports a composite spread of **0.063** and an ordering. That ordering has never been checked against run-to-run variance, and the corpus is known to be narrow: the four models are close relatives spanning 0.886–0.949, and the difficulty tiers are **not monotonic** (easy 0.951, medium 0.890, hard 0.931 — "hard" scores *above* "medium"). A non-monotonic tier profile is what noise looks like. Before any gap is reported, the framework must be able to say whether it exceeds the noise.

There is a second, cheaper question the framework cannot currently answer: **can this corpus discriminate at all?** One weak model in the bank answers it — if the corpus spreads a weak model apart from the strong ones, the "tie" is a narrow bank; if even a weak model lands at 0.9, the corpus is the problem. That is one model × 20 specs, and it is the highest-value single measurement available.

## What Changes

- **Repeat every (model, spec) pair k times.** Each attempt carries a `repeat` index; results from different repeats of the same pair are distinct records. Default `k = 1` (no behaviour change unless asked).
- **Report variance, not just a mean.** Per model: mean, min, max, and standard deviation of the composite, with the same for each dimension. Per spec: the same, so an unstable spec is visible.
- **A variance guard, separate from the two existing guards.** When a model's within-model standard deviation exceeds a threshold, the run is flagged: any gap smaller than roughly twice the standard deviation is noise. Threshold and rule recorded with the run.
- **Add a deliberately weak model to the bank** so the corpus's ability to discriminate is measured, not assumed. Cheap: one small model alongside the existing four.
- **Logging that explains a run without being noisy.** One line per repeat (suppressed by default, shown with `-v`), one summary line per model, and a one-line reason when a guard fires. A reader should be able to read the tail of a log and know what happened.
- **Name the measurement honestly.** The framework reports *stability across repeats* (mean and spread). It does **not** report `pass@k` in the benchmark sense ("did it pass at least once in k tries") — that is a generosity measure and is a different question, deliberately not added.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `eval-scoring`: aggregation gains repeat awareness and per-model/per-spec variance reporting, and a variance guard alongside the degenerate and exclusion-rate guards.
- `code-execution`: an attempt gains a `repeat` index and results are grouped by `(model, spec)` for stability reporting.
- `eval-cli`: `run` gains a repeat count and a verbosity flag; the logging contract for repeats, summaries, and guard reasons is specified.

## Impact

- `models.py` — `repeat` on the attempt result and the run; a variance block on aggregates; schema version bump.
- `pipeline.py` — the `(spec, model)` pair loop becomes a `(spec, model, repeat)` loop; retry policy is unchanged and applies within a repeat.
- `scoring/aggregate.py` — repeat-aware grouping, variance statistics, and the new guard.
- `reporting.py` — variance columns and a stability section; a per-spec variance table.
- `cli.py` — `--repeats k`, `-v/--verbose`, and the log lines.
- `config.py` — the default repeat count and the variance threshold.
- **Runs get slower in proportion to k**, bounded by the repeat count. The default stays 1.
- **The schema version bumps again**, so results from before this change are marked historical for the same reason as the last two: they carry no variance information.
