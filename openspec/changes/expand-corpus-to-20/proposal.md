# Proposal

## Why

The 15-spec corpus fails to differentiate the four models in the default bank. A live run scored every model 1.00 on `execution` and 1.00 on `edge` for nearly every spec; the ranking rested almost entirely on the style dimension, which measures tidiness rather than capability. The corpus is too easy, so it cannot answer the question it exists to answer. Adding harder specs while keeping the existing ones preserves the current evidence and adds a range where models can actually separate.

## What Changes

- Add 5 new specs, bringing the corpus from 15 to 20. Difficulty balance goes from 5/5/5 to 5/5/10, so most new work is at the `hard` tier.
- Keep all 15 existing specs unchanged, including their prompts, tiers, tags, reference solutions, and both hidden suites. No existing score becomes incomparable with a new one.
- Choose the 5 new specs so they stress things the current corpus under-tests: state machines over untrusted input, resource limits, precision and floating-point behaviour, ordering under partial failure, and multi-step protocols. These are areas where a plausible-looking solution commonly fails the edge suite.
- Give each new spec a hidden edge suite that is deliberately harder than the ground-truth suite, so `edge` is a genuine separator rather than a copy of `execution`.
- Re-run corpus self-validation to confirm all 20 references pass both of their suites.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `spec-corpus`: the corpus-size and tier-balance requirements change from "at least 15 specs, at least 5 per tier" to "at least 20 specs, at least 5 easy, at least 5 medium, at least 10 hard". The requirement also gains an explicit expectation that the hidden edge suite is strictly harder than the ground-truth suite, since a weak edge suite is what allowed the current corpus to collapse onto style.

## Impact

- New directories under `corpus/`, one per new spec, each with `spec.json`, `solution.py`, `test_ground_truth.py`, and `test_edge_cases.py`.
- `tests/test_corpus.py` assertions on corpus size and tier balance need their thresholds updated from 15 to 20.
- `docs/corpus.md` tier table and counts need updating.
- Reports generated before this change remain valid and are not re-run; the mock quickstart remains the offline path.
- Runtime cost grows proportionally: a 4-model × 20-spec run is 80 evaluations rather than 60.
