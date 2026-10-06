# Proposal

## Why

The first repeat-stability measurement (`reports/results-live20-v4.json`, 300/300 attempts scored, 0 excluded) answered the question the previous change was built to ask, and the answer is unambiguous: **the corpus cannot discriminate models.**

- The four subjects span **0.926–0.949**, and the top two are within **0.002**. Applying the pre-registered rule, no ordering is reportable.
- The deliberately weak control (`opencode-go/qwen3.8-flash`, a small flash model) landed at **0.927 — mid-pack**. It was **not separated** from three pro models. The model bank is not the limiting factor.
- **58 of 60 subject attempts pass every ground-truth test.** Execution is 0.981–0.997; edge is 0.969–0.999. The only dimension with headroom is `style` (0.654–0.758), and the composite is capped near 0.95 by the weights.

The failure is therefore **not** that the prompts are ambiguous. It is that the hidden test suites are too easy: a competent model passes them, so every model lands in the same narrow band. The previous change proved this with a control model; this change acts on the proof.

## What Changes

- **Add 10 new hard specs** under `corpus/`, each with a solution and two hidden suites (ground truth and edge). The 20 existing specs are left untouched, so existing runs remain comparable.
- **Make the hidden tests the discriminator.** A new spec qualifies only if its tests genuinely fail competent models — the recipe targets precise multi-constraint compliance, adversarial edge cases, and algorithmic subtlety, not longer prompts.
- **Every new spec is an original problem**, not a famous one. This addresses difficulty and uncontrolled training-data contamination together: a problem the model has not memorised is both harder and a cleaner measurement.
- **A pre-registered acceptance rule, fixed before any calibration run.** A batch of candidate specs is accepted only if a calibration run separates the control from the subjects, or lowers a subject below a stated threshold. Deciding "hard enough" after seeing the numbers is how a benchmark rationalises itself.
- **Corpus validation stays mandatory.** Every new reference solution must pass its own two suites (`validate`), so a broken spec cannot masquerade as a hard one.
- **Report the new tier honestly.** If the new specs still fail to discriminate, that is the finding, and the next step is a different difficulty axis — not a claim that the corpus works.

## Capabilities

### New Capabilities

- `corpus`: spec soundness (a reference passes its own hidden suites), spec difficulty as an acceptance criterion, and the batch calibration rule that decides whether a set of new specs is hard enough to keep.

### Modified Capabilities

- `eval-scoring`: a report states the corpus size a run was computed over, and marks aggregates from different corpus sizes as not directly comparable.

## Impact

- `corpus/<spec-id>/` — 10 new spec directories, each with `spec.json`, `solution.py`, `test_ground_truth.py`, `test_edge_cases.py`.
- `docs/roadmap.md` — the corpus-credibility item moves from "planned" to reflect what the measurement showed.
- **The corpus grows 20 → 30 specs.** Older runs cover 20 specs and stay readable; they are not re-scored. A run over 30 specs is not directly comparable to a run over 20 in the aggregate, and the report says so.
- **Calibration costs one run.** 5 models × 30 specs at `--repeats 2` is 300 generations — comparable to the last run, under a few dollars.
- **This change does not touch scoring, providers, or the CLI.** It is a corpus change plus the acceptance rule that judges it.
