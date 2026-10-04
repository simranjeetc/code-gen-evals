# Design

## Context

See `proposal.md`. The measured state that drives this design, from `reports/results-live20-v3.json`:

```
objective composite per model        spread
deepseek-v4.1-flash      0.949
deepseek-v4-pro          0.941
mimo-v2.6-flash          0.928
longcat-2.5-preview-free 0.886       0.063

per tier:  easy 0.951 | medium 0.890 | hard 0.931
```

Two facts matter:

1. **The ordering has never been tested against noise.** Every model's score is one sample. A 0.063 spread could be entirely repeat variance.
2. **The tier profile is non-monotonic.** Hard (0.931) scores above medium (0.890). If the corpus were difficulty-ordered, that would be surprising. It is what noise looks like, and it is a warning that the current "hard" tier may not be hard.

**The scoring meaning is fixed here, before any data exists.** This is deliberate: the failure mode this project keeps hitting is a number that looks like a finding. Deciding what counts as a finding *after* seeing the numbers is how that happens.

## Goals / Non-Goals

**Goals:**

- Measure whether a model's score is repeatable, so a gap can be compared against noise.
- Make an unstable spec or an unstable model visible rather than averaged away.
- Measure whether the corpus can discriminate at all, using a deliberately weak control model.
- Keep logging quiet enough that a normal run prints almost nothing, loud enough that the tail of a log explains the run.

**Non-Goals:**

- Best-of-k or "did it eventually pass". That is a generosity measure; we want spread.
- Changing what the corpus asserts, or any existing scoring formula.
- Re-scoring history. Old results carry no repeat information and stay as history.
- Adding harder specs *in this change*. Harder specs are the response to what this change measures, not part of it.

## Decisions

### D1: Report spread, and name it repeat stability — not `pass@k`

`pass@k` answers "did it pass at least once in k tries?" — a measure of luck. We want the opposite: how much the *same* model varies. Reporting a spread figure under the name `pass@k` would be a category error, and this project has already paid for category errors.

- Data, CLI and report use **repeat stability** / **spread**.
- The report states: this measures repeatability, not eventual success.
- Alternative considered: best-of-k. Rejected — it measures the corpus, not the model, and it rewards a model that got lucky once.

### D2: A repeat is k independent attempts; a retry is not one of them

The repeat loop is the outer loop; the existing retry policy runs *inside* a repeat.

- Why: the retry exists so a transient failure is not recorded as a model failure. Counting a retry as an extra repeat would let a flaky provider inflate the sample.
- Consequence: attempts = k × (1 + retries), and the repeat count records k, not the attempts.

### D3: Statistics are computed over `scored` attempts only

The exhausted attempt record already exists for the *n* and *excluded* columns. Repeat stability reuses it.

- Per model and per spec: **mean, min, max, standard deviation** of the composite over scored repeats.
- If a pair has fewer than two scored repeats, its spread is **not measured**, not zero.
- Why this matters: reporting `sd = 0.00` when only one repeat ran would look like *evidence of stability*. It is absence of evidence, and the report must say so. This is the same defect class as a failure scored as zero.

### D4: The variance guard fires on a model's within-model standard deviation

Separate from the two existing guards, because it says a third, different thing.

| guard | catches |
| --- | --- |
| degenerate | every model scored identically — the corpus measured nothing |
| exclusion-rate | too many attempts were not measurements at all |
| **variance** | a model's own score is not repeatable, so its gap to others is not readable |

- **Threshold, fixed now:** `sd > 0.05` on the composite marks the run `unstable` and names the model.
- **Interpretation rule, fixed now:** a gap between two models is **not distinguishable from noise** unless it exceeds roughly `2 × sd`. With the current 0.063 spread this is decisive:
  - `sd ≤ 0.015` → the 0.063 spread is ≥ 4× noise → the ordering is real.
  - `0.015 < sd ≤ 0.031` → the spread is 2–4× noise → ordering real, individual gaps not.
  - `sd > 0.031` → the spread is under 2× noise → **do not report an ordering.**
- Why 0.05 and 2×: 0.05 is a threshold a composite gap must clear to be worth reporting, and 2×sd is the conventional floor for calling two means different. Both are recorded with the run so a later run can be judged against the rule that existed when it was made, not a rule invented afterwards.

### D5: A deliberately weak control model is part of the measurement

The cheapest way to learn whether the corpus discriminates is to include something it *should* be able to fail.

- Add one cheap, small model from the available bank to the comparison — `opencode-go/deepseek-v4-flash` or `opencode-go/qwen3.8-flash`, whichever is cheapest to run.
- The report states plainly which of the two outcomes occurred: the control was separated (corpus discriminates; the narrow spread is a property of the bank), or it was not (the corpus cannot discriminate, and harder specs are the fix).
- Why a control and not "more models": more relatives would reproduce the tie. A control is designed to break it if it can be broken.
- Alternative considered: add harder specs first. Rejected — without the control you cannot tell whether harder specs were needed or whether the bank was simply narrow, which is the same unfalsifiable position we are in now.

### D6: Logging is one line per attempt, one line per model, one line per guard

The default must stay quiet.

```
# default (one line per model at the end)
  deepseek-v4.1-flash   mean=0.949 sd=0.012 min=0.93 max=0.97  n=60 scored=60 excluded=0
# only printed when a guard fires
  UNSTABLE: mimo-v2.6-flash sd=0.071 exceeds 0.050 — gaps under 0.14 are noise

# with -v (per attempt)
  repeat 2/3  json_diff  mimo-v2.6-flash  outcome=scored  composite=0.94  12.3s
```

- Every line is self-describing: it names the model, the spec, the repeat and the value.
- `-v` adds attempts and does not change the summary.
- Why this shape: the request was "not too verbose, but I can tell what happened". One line per model is the smallest thing that answers "how did it go, and was it stable"; `-v` is the escape hatch for "why did that one spec do that".
- Alternative considered: structured JSON logs. Rejected for interactivity — a human is reading the terminal. The results file already carries the machine-readable form.

### D7: Bump the schema version

Attempts gain a `repeat` index and the run gains a repeat count and variance blocks, so older files are explicitly stale rather than silently variance-free.

- Consistent with the last two changes, and stated for the same reason.

### D8: Documentation lands with the code

The same task group updates `docs/scoring.md`, `docs/report.md` and `docs/roadmap.md` (moving pass@k out of "planned"), because the last three defects were each partly a documented behaviour that disagreed with the code.

## Risks / Trade-offs

- [Runs are k× slower] → Default stays 1; repetition is opt-in and chosen. k=3 over 20 specs × 5 models is 300 generations.
- [Variance makes a previous "finding" disappear] → That is the finding. A spread that does not clear 2×sd was never reportable.
- [A control model may cost a little] → One cheap model over 20 specs. It is the cheapest measurement in the backlog.
- [A threshold of 0.05 is a judgement] → Yes, and it is recorded with the run so it can be revisited with evidence rather than quietly moved.
- [Variance may be concentrated in `semantic`] → Plausible: the judge is the only non-deterministic axis, and judge-provider timeouts already showed up. The per-dimension spreads will show whether composite variance is mostly the opinion; if so, the objective composite may be far more stable than the composite, and that is worth reporting.
- [Adding a control model changes the comparison set] → Older runs become incomparable for the same reason as before; said plainly, and the control is reported as a control, never ranked as a peer.

## Migration Plan

No migration. Existing results remain readable under their schema version and are marked historical. Rollback is reverting to a single repeat (the default) and removing the variance guard.

## Open Questions

- Whether variance is dominated by `semantic` is an empirical question this change answers; it is not a design decision, and no threshold is set for it in advance.
- The exact control model is chosen at run time from the available bank on cost grounds; the design fixes the *role*, not the id.
