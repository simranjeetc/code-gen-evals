# Design

## Context

See `proposal.md` for the motivation and `docs/roadmap.md` for the wider backlog.

Measured state that shapes this design, from `reports/results-live20.json` (4 models × 20 specs):

| model | execution | edge | semantic | style |
| --- | --- | --- | --- | --- |
| deepseek-v4.1-flash | 1.000 | 0.993 | 1.000 | 0.720 |
| deepseek-v4-pro | 0.967 | 0.984 | 0.933 | 0.676 |
| longcat | 0.950 | 0.950 | 0.933 | 0.621 |
| mimo | 0.880 | 0.887 | 0.882 | 0.677 |

Semantic abstained on 13 of 80 results. Three results were **infrastructure failures** (two timeouts, one provider crash) scored `0.00`, which is a separate defect addressed by its own change.

Two facts drive the decisions below:

1. **Three of the four dimensions are already model-free and objective** — two test suites and a deterministic analyser. Only `semantic` depends on a judge.
2. **Composites are currently computed over all four**, so an opinion is weighted at 0.25 alongside three objective measurements.

## Goals / Non-Goals

**Goals:**

- Make the semantic score stable enough that two runs of the same code do not drift.
- Stop presenting a judge's opinion as if it were a measurement.
- Produce a disclosure number for how reliable the judge is.

**Non-Goals:**

- Human annotation at scale. One small spot check is in scope as validation; a proper annotation study is not, and would need budget and people.
- Removing the semantic dimension. It catches a real class of failure (passes tests, misses intent) that nothing else can.
- Making semantic "objective". It cannot be, and pretending otherwise is the defect.
- Re-running historical results. They stay on disk as history and are marked incomparable.

## Decisions

### D1: Anchor the judge to the reference solution, do not ask for an absolute score

The judge receives the requirement, the **reference solution**, and the candidate, and answers whether the candidate is equivalent to, worse than, or better than the reference.

- Why: an absolute rubric makes the judge invent a scale on every call, which is the drift we are fixing. A reference pins the scale down. This is the same reason pairwise benchmarks (MT-Bench, AlpacaEval) dominate absolute-score benchmarks.
- Why it is safe here: the reference is hidden from the *model under test* and from no one else. Showing it to the judge leaks nothing to the subject.
- Alternative considered: keep absolute scoring and add a ladder only. Rejected as insufficient — a ladder narrows variance but still leaves the judge without an anchor for this particular task.

### D2: Add a worked ladder as well as the anchor

The prompt carries a concrete 1.0 / 0.5 / 0.0 example.

- Why: cheap (one paragraph), and it makes the bands explicit rather than inferred.
- Alternative considered: ladder only, no anchor. Rejected — it is D1 that fixes drift; the ladder just reduces wobble.

### D3: Remove `semantic` from the composite

The composite covers `execution`, `edge`, `style`. Semantic is reported as its own column, clearly labelled as judge-derived.

- Why: this is the honest fix. A reader seeing one number must not be consuming an opinion blended with measurements. Marking it is not enough if it still changes the number.
- Consequence accepted: the composite becomes *narrower* — it no longer reflects "does it do what was asked", only "does it work, survive, and read well". That is a real loss of coverage, and the report must say so rather than quietly shrinking what it measures.
- Alternative considered: keep semantic in the composite but at a low weight (0.1). Rejected — an opinion at any weight is still an opinion inside a measurement, and the whole point is to separate them.

### D4: Rebalance the objective weights to sum to 1.0

Dropping semantic from 0.25 frees that mass. Proposed redistribution: `execution` 0.5, `edge` 0.3, `style` 0.2.

- Why: execution is the primary question; edge is the differentiator this corpus was built to expose; style stays visible but does not dominate.
- Alternative considered: keep the old weights and renormalise mechanically (0.53/0.33/0.13). Rejected — mechanical renormalisation leaves style with a weight nobody chose.

### D5: Measure agreement across two judge models, over the references

Both judges score the same 20 reference solutions. Agreement is reported as exact-match rate plus mean absolute difference.

- Why the references and not random outputs: the references are the only known-correct set, so disagreement there is a pure judge artefact rather than a judgement call about ambiguous code.
- Why two judges is not a baseline: it measures *stability*, not correctness. Two judges from the same vendor can share a bias and agree. It is disclosed as stability, never as validation.
- Alternative considered: golden reference instead, and wait for human annotation. Rejected for this change — two-judge agreement is cheap, and the proposal is explicit that only human agreement can validate correctness.

### D6: Human spot check is a separate, later step

The only measurement that answers "is the judge right" is a human agreeing with it. That is deferred to its own change, deliberately:

- It needs ~30 minutes of human time, which is not available in the session that does this work.
- There is no point asking a human to validate a judge that is known to be badly designed. Anchor it first, then validate.

### D7: Mark semantic as derived in the data, not only in prose

The result schema records that the score is judge-derived and by which model. Prose labels can be missed or dropped; a field cannot.

## Risks / Trade-offs

- [All existing results become incomparable] → Stated explicitly in `proposal.md` and in the report footer. Historical files stay on disk, marked with the judge design that produced them.
- [The composite now measures less] → The report must say what it excludes. A narrower, honest composite beats a wider, contaminated one.
- [Reference-anchored judging may be *less* discriminating on easy specs] → If the reference is obviously correct, both a good and a mediocre candidate may read as "equivalent". Mitigated by keeping the ladder and by the edge dimension, which still separates. To be checked against the existing per-spec spread after the change.
- [Two judges agreeing may be mistaken for validation] → Documented as stability only, in both the design and the report text.
- [Judge cost rises] → The prompt now carries a reference solution, roughly doubling input tokens. At the models in use this is fractions of a cent per call.
- [The judge may over-weight superficial similarity to the reference] → Explicitly warned against in the prompt: a candidate that matches the reference's shape but not its behaviour must not score 1.0.

## Migration Plan

No migration. Existing `reports/*.json` remain valid under the old schema and are left in place. New runs carry the judge design in their metadata. Rollback is reverting the judge prompt and restoring semantic to the composite weights.

## Open Questions

- Whether reference-anchored scoring makes the semantic dimension *too* lenient on easy specs is an empirical question answered by comparing per-spec scores before and after, not a design decision.
