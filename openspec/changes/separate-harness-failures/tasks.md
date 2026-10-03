# Tasks

## 1. Outcome classification

- [ ] 1.1 Add an `outcome` field to the attempt result with values `scored`, `timeout`, `provider_error`, `unparseable_output`, `not_attempted`, plus the provider message; verify each round-trips through JSON and the schema version is bumped
- [ ] 1.2 Classify timeouts and non-zero provider exits in the OpenCode provider; verify a simulated timeout produces outcome `timeout`, not a zero score
- [ ] 1.3 Classify the same cases in the Claude Code provider; verify a simulated timeout and a simulated `is_error` produce the matching outcome
- [ ] 1.4 Classify unparseable output separately from provider failure; verify a response with no code block produces `unparseable_output`
- [ ] 1.5 Keep a sandbox crash (import error, infinite loop, wrong output) classified as `scored`; verify by running a broken candidate and confirming the outcome is `scored`

## 2. Exclusion-aware aggregation

- [ ] 2.1 Compute per-model, per-tier and per-task-type aggregates over `scored` attempts only; verify an excluded attempt does not change any average
- [ ] 2.2 Report excluded counts alongside every aggregate; verify the counts appear in the saved results and match the raw data
- [ ] 2.3 Verify the recomputation matches by hand: remove excluded results independently and confirm identical averages
- [ ] 2.4 Verify semantic abstentions and infrastructure exclusions are counted separately, since they are different things

## 3. Retry policy

- [ ] 3.1 Retry a transient failure once with a longer budget; verify a simulated timeout that succeeds on retry is recorded as scored with the retry noted
- [ ] 3.2 Bound retries so a permanently failing attempt is recorded once; verify exactly two attempts are made, not more
- [ ] 3.3 Verify a non-transient failure (unparseable output) is not retried
- [ ] 3.4 Raise the default provider timeout and verify a large hard spec that previously timed out now completes

## 4. Exclusion-rate guard

- [ ] 4.1 Mark a run `unreliable` when a model's exclusion rate exceeds a configurable fraction; verify with a constructed fixture above and below the threshold
- [ ] 4.2 Name the affected models in the flag; verify the names appear in results and in the report
- [ ] 4.3 Verify an unreliable run still writes its results and still exits non-zero
- [ ] 4.4 Verify the guard is independent of the degenerate guard: a run can be unreliable without being degenerate, and degenerate without being unreliable

## 5. Reporting

- [ ] 5.1 Add a reliability section listing every infrastructure failure with its outcome and message; verify it renders and that failures are excluded from the tables but visible here
- [ ] 5.2 Show exclusion counts next to per-model aggregates; verify a reader can see how many attempts each average is based on
- [ ] 5.3 State plainly when a run is unreliable and which models are affected; verify the wording appears and is prominent
- [ ] 5.4 Verify the report never presents a failed attempt as a low model score anywhere in the tables

## 6. Falsify the original finding

- [ ] 6.1 Re-run the four-model bank over the full corpus under the new classification; verify the run completes
- [ ] 6.2 Confirm the previously hand-computed corrected spread matches the reported spread; record both numbers
- [ ] 6.3 Record the observed exclusion rate for each model, and whether retries recovered the failures
- [ ] 6.4 Update `docs/execution.md` and `docs/scoring.md` to describe outcome classification, exclusion, retries and the guard; verify every claim in the docs matches observed behaviour
