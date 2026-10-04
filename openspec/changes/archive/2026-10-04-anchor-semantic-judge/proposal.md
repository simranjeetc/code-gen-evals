# Proposal

## Why

The `semantic` dimension asks a judge model for an absolute score from 0.0 to 1.0 with nothing to anchor the scale. Each call, the judge invents its own standard. This produces three problems:

1. **Drift.** The same code can score differently across calls because there is no fixed reference point.
2. **Unvalidated trust.** The score is blended into the composite at weight 0.25 as if it were an objective measurement, alongside three dimensions that are genuinely objective (two test suites and a deterministic analyser).
3. **No disclosed reliability.** No number exists for how often the judge agrees with a human, or even with another judge. A reader has no way to know how much to trust it.

This is the same class of defect as the two already found and fixed in this project — a failure rendered as a confident number. See `docs/roadmap.md` entries on failure-as-score.

## What Changes

- **Anchor the judge to the reference solution.** The judge is given the task requirement, the reference solution, and the candidate, and asked to compare the candidate against the reference rather than inventing an absolute standard. This is the design used by the pairwise-scoring benchmarks (MT-Bench, AlpacaEval), which dominate precisely because absolute scoring drifts.
- **Add a worked-score ladder** to the judge prompt: a concrete example of what a 1.0, a 0.5, and a 0.0 look like, so the bands are defined rather than inferred.
- **Remove `semantic` from the composite.** Report it as its own opinion column. The composite is recomputed over the three objective dimensions only, with weights renormalised.
- **Record judge agreement** for the same 20 reference solutions across two different judge models, and store the number alongside results so it can be disclosed.
- **Mark the semantic dimension as judge-derived** in every report and result file, so no consumer can mistake it for a measurement.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `eval-scoring`: the semantic dimension is redefined as reference-anchored rather than absolute; the composite is redefined to cover objective dimensions only; a new requirement covers judge-agreement measurement and its disclosure.

## Impact

- `scoring/semantic.py` — judge prompt, comparison framing, ladder.
- `scoring/aggregate.py` — composite weights cover `execution`, `edge`, `style` only; `semantic` is carried separately.
- `pipeline.py` — the reference solution is passed to the judge.
- `reporting.py` — semantic shown as a distinct, clearly labelled column; agreement figure surfaced.
- **Existing results become incomparable.** Every saved run under `reports/` was produced under the old absolute-scoring judge and the old composite. They stay on disk as history but must not be compared against new runs. This is stated rather than hidden because it is a real cost of the change.
- Judge API cost roughly doubles per semantic call (a longer prompt), which is still negligible.
