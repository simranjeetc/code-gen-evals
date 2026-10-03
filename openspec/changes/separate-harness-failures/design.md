# Design

## Context

See `proposal.md` for the motivation. The measured evidence that drives this design, from a four-model run over the full 20-spec corpus:

```
model                    incl. failures   excluding failures
deepseek-v4.1-flash          0.969            0.969
longcat                      0.914            0.962     ← moved +0.048
mimo                         0.859            0.954     ← moved +0.095
deepseek-v4-pro              0.935            0.935
spread                       0.110            0.035
```

Three of eighty attempts failed for infrastructure reasons:

```
timeout (180s)  mimo-v2.6-flash  × money_total
timeout (180s)  mimo-v2.6-flash  × template_renderer
exit 1          longcat          × money_total
```

The conclusion drawn from the uncorrected numbers — "the new corpus broke the tie" — was wrong. The tie is unchanged. This design exists so that mistake cannot be made silently again.

## Goals / Non-Goals

**Goals:**

- Make a harness failure impossible to mistake for a model failure, in the data and in the report.
- Recover transient failures automatically rather than recording them.
- Make a run that is mostly harness failures announce itself.

**Non-Goals:**

- Preventing infrastructure failures. Networks drop and models hang; the goal is honest accounting, not zero failures.
- Retrying indefinitely. One extra attempt, then record and move on.
- Changing what the test suites assert, or any scoring formula.
- Re-scoring historical results. They stay as history under the old schema version.

## Decisions

### D1: Classify at the provider boundary, not in the scorer

`outcome` is set where the failure is observed — the provider and the execution runner — not inferred later from a score of zero.

- Why: by the time a `0.0` reaches the scorer, the information is gone. Inferring "this zero was probably a timeout" from downstream data is guesswork.
- Alternative considered: infer in aggregation by checking for an empty code field. Rejected — an empty code field is also what an unparseable response looks like, and the two need different handling.

### D2: A sandbox crash is `scored`; a harness crash is `provider_error`

The distinction is *whose fault it is*, not whether an error occurred.

- A model that imports nothing, loops forever, or prints the wrong answer is a **scored** result. The harness did its job.
- A provider that times out, or a runner that cannot start, is an **infrastructure failure**. The model was never fairly tested.
- Why it matters: a model with a broken environment must not be recorded as bad at coding. It was not measured at all.

### D3: Exclude from aggregates, but never hide

Excluded attempts are removed from averages and listed explicitly with their outcome and message.

- Why both: excluding and hiding would let a broken run look clean; including would deflate a model for the harness's fault.
- The report shows exclusion counts next to every aggregate, so a reader always knows the denominator.
- Alternative considered: score failures as `0.0` but flag them. Rejected — that is close to the current behaviour and it is what produced the false finding.

### D4: One retry, with a longer budget, only for transient outcomes

`timeout` and `provider_error` are retried once at a raised timeout. `unparseable_output` and `not_attempted` are not.

- Why retry at all: two of the three observed failures were timeouts on a spec that other models completed, so they were plausibly transient.
- Why only once: a model that genuinely hangs must not double the run's cost. The observed failure mode is occasional, not systematic.
- Why not retry unparseable output: the model answered and the answer was unusable. Retrying on the same prompt is unlikely to change that, and if it did it would be recording a lucky second draw as the model's ability.
- Alternative considered: retry with the same budget. Rejected — a timeout at 180s would simply time out again.
- **On the raised default timeout specifically:** 180s was too tight for the largest hard specs. The new default is set from the observed distribution of successful call durations rather than guessed, and the value chosen is recorded with the run.

### D5: The exclusion-rate guard is separate from the degenerate guard

Two independent conditions, both fatal to the run's conclusions:

| guard | catches |
| --- | --- |
| degenerate | every model scored identically — the corpus measured nothing |
| exclusion-rate | too many attempts were not measurements at all |

- Why separate: they can occur independently, and a run can be one, both, or neither. Merging them would lose which problem occurred.
- Threshold: configurable, defaulting to a fraction that would have caught the observed run had it been worse. Chosen from the evidence, not by taste.

### D6: Bump the schema version

Results gain an `outcome` field and change their meaning, so older files are explicitly stale rather than silently incomparable.

- Why: a consumer reading both a new and an old results file must be able to tell that the old one scored failures as zeros.

### D7: Documentation is a task, not an afterthought

Every change in behaviour lands with its docs updated in the same task group it belongs to. This was written into the task list deliberately, because the last two defects were both partly caused by a documented behaviour that did not match the code.

## Risks / Trade-offs

- [Retries make runs slower] → Bounded to one extra attempt per transient failure; most attempts fail zero times.
- [A raised timeout makes genuine hangs costlier] → Bounded by the retry cap and by the per-suite timeout, which is separate and unchanged.
- [Excluding failures can flatter a model whose infrastructure is flaky] → The exclusion count is always reported, and the exclusion-rate guard fires when it is material. A model with a high exclusion rate is flagged, not rewarded.
- [Classifying at the provider means touches in several files] → Accepted; the alternative loses the information. A single shared classification helper keeps the rules in one place.
- [The schema bump invalidates saved runs] → Stated in the proposal. Historical files are kept and marked.
- [Referencing the previous false finding in the docs could look like over-correction] → It is recorded because it is the justification for the change, and because step 6.2 re-checks it against the new numbers.

## Migration Plan

No migration. Old result files remain readable at their old schema version and are marked stale in the report footer. Rollback is reverting the classification, restoring zero-scoring for failures, and reverting the timeout default.

## Open Questions

- The exact exclusion-rate threshold is set from the observed evidence and may need revisiting once more runs exist; it is configurable for that reason, not because the value is unknown now.
