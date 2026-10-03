# Tasks

## 1. Corpus growth: five new hard specs

- [x] 1.1 Author `template_renderer` (state machine over untrusted text): `spec.json`, `solution.py`, `test_ground_truth.py`, `test_edge_cases.py`; verify the reference passes both suites and that a naive `str.replace`-based candidate fails the edge suite
- [x] 1.2 Author `bounded_queue` (resource limits): all four files; verify the reference passes both suites and that an uncapped candidate fails the edge suite
- [x] 1.3 Author `money_total` (numeric precision): all four files; verify the reference passes both suites and that a float-accumulating candidate fails the edge suite
- [x] 1.4 Author `batch_processor` (partial failure and ordering): all four files; verify the reference passes both suites and that a fail-fast candidate fails the edge suite
- [x] 1.5 Author `state_machine` (multi-step protocol with mid-protocol abort): all four files; verify the reference passes both suites and that a happy-path-only candidate fails the edge suite
- [x] 1.6 Tag all five with task types that widen the tag vocabulary rather than duplicating it, and confirm each is tier `hard`

## 2. Edge-suite discipline

- [x] 2.1 Add a test asserting that no spec's edge suite duplicates any test id from its ground-truth suite
- [x] 2.2 Add a test asserting that each new spec's edge suite contains at least one test covering a failure mode the ground-truth suite does not exercise
- [x] 2.3 Verify the edge-suite rule for all five new specs by running a deliberately naive candidate per spec and confirming it fails `edge` while the reference passes it

## 3. Framework updates

- [x] 3.1 Raise the corpus-size and tier-balance assertions in `tests/test_corpus.py` from 15 to 20 and from hard ≥ 5 to hard ≥ 10; verify the suite passes
- [x] 3.2 Confirm `validate` reports all 20 specs sound with 40 suite runs and exits zero
- [x] 3.3 Update the tier table and counts in `docs/corpus.md`; verify every count in the doc matches `list-specs` output
- [x] 3.4 Confirm the prompt-isolation test still passes for the five new specs (no test code, test ids, or reference lines in any prompt)

## 4. Acceptance: does the bigger corpus actually separate the bank?

- [x] 4.1 Run the full mock pipeline over all 20 specs and confirm the run is not marked inconclusive
- [ ] 4.2 Run the default model bank over the full 20-spec corpus and confirm at least two distinct composites
- [ ] 4.3 Confirm the 15 pre-existing specs still produce the same per-spec scores as `reports/results-live.json`, proving the change is purely additive
- [ ] 4.4 Record the new run's per-dimension and per-tier spread; if the bank still ties, state that plainly rather than presenting the ranking
- [ ] 4.5 Re-render `reports/report-live.md` from the new results and confirm the corpus size, tier counts, and task-type buckets in the report match the corpus
