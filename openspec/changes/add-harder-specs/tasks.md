# Tasks

## 1. Author the ten specs

- [ ] 1.1 Write the ground-truth and edge suites for `version_range_eval` test-first against a plausible-but-wrong implementation; verify the naive solution passes ground truth and fails edges
- [ ] 1.2 Write the suites for `cron_next_run` test-first; verify the naive solution passes ground truth and fails edges on wraparound and step cases
- [ ] 1.3 Write the suites for `unit_conversion_graph` test-first; verify a naive conversion-only solution fails the inconsistency and unreachable cases
- [ ] 1.4 Write the suites for `interval_map_query` test-first; verify a naive solution fails the boundary and overlap cases
- [ ] 1.5 Write the suites for `patch_apply` test-first; verify a naive line-index solution fails the offset and reject cases
- [ ] 1.6 Write the suites for `sql_where_null_logic` test-first; verify a two-valued-logic solution fails the NULL cases
- [ ] 1.7 Write the suites for `exact_split` test-first; verify a per-part-rounding solution fails the total-preservation cases
- [ ] 1.8 Write the suites for `event_replay` test-first; verify a naive in-order solution fails the idempotency and out-of-order cases
- [ ] 1.9 Write the suites for `type_inference` test-first; verify a naive inference fails the overload and corner cases
- [ ] 1.10 Write the suites for `config_deep_merge` test-first; verify a naive dict-merge fails the list-append and conflict cases
- [ ] 1.11 Write each spec's reference solution and `spec.json` (id, title, tier=hard, tags naming its axis, prompt, required_symbols); verify each reference passes both its suites in full

## 2. Corpus soundness

- [ ] 2.1 Run corpus validation over the 30 specs; verify every reference passes 100% of both suites and 0 specs are unsound
- [ ] 2.2 Verify each new spec has a non-empty ground-truth suite and a non-empty edge suite
- [ ] 2.3 Verify no new spec restates an existing spec's problem; record the check
- [ ] 2.4 Verify the corpus still reports the original 20 specs unchanged and their tier counts unchanged
- [ ] 2.5 Verify the corpus lists 30 specs with the expected tier counts (easy 5, medium 5, hard 20)

## 3. Calibration run

- [ ] 3.1 Run the 4 subjects plus the control over the 10 new specs at `--repeats 2`; verify it completes with 0 excluded and no guard firing
- [ ] 3.2 Verify the run's schema, logging and per-model spread render as expected over the new specs
- [ ] 3.3 Record, per new spec, whether at least one model failed at least one of its tests; verify the count of discriminating specs

## 4. Apply the pre-registered rule

- [ ] 4.1 Compute `subject_spread`, `control_gap` and `noise` over the new specs; verify the computation against the design's definitions
- [ ] 4.2 Apply the acceptance rule from D4 exactly as written; verify the accept/reject decision follows the rule and not a post-hoc adjustment
- [ ] 4.3 Verify at least 7 of 10 specs discriminate, or record which did not and why
- [ ] 4.4 If accepted, verify the control is separated or the subject spread exceeds 0.10 with top-subject sd at or below 0.031
- [ ] 4.5 If rejected, record the result plainly and state the next difficulty axis (roadmap 6 or 8) rather than moving a threshold
- [ ] 4.6 Record the rule, the thresholds and the observed figures together in the change

## 5. Comparability and reporting

- [ ] 5.1 Verify the report states the corpus size for a run
- [ ] 5.2 Verify a run over 30 specs is marked not directly comparable with a run over 20 in the aggregate
- [ ] 5.3 Verify a previous 20-spec results file still loads and renders unchanged
- [ ] 5.4 Add a test asserting the corpus-size comparability statement is present

## 6. Documentation

- [ ] 6.1 Update `docs/roadmap.md`: record what the measurement showed and move the corpus-credibility item out of "planned" to reflect the licensed work
- [ ] 6.2 Update `docs/scoring.md`: state that difficulty is a tested property and how a spec batch is accepted
- [ ] 6.3 Verify every claim in the docs matches observed behaviour, not intent
