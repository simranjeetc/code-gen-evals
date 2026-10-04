# Tasks

## 1. Repeat the attempts

- [x] 1.1 Add a `repeat` index to the attempt result and a repeat count to the run; verify both round-trip through JSON and the schema version is bumped
- [x] 1.2 Make the pipeline loop over `(spec, model, repeat)` instead of `(spec, model)`; verify a repeat count of 3 produces three distinct attempts per pair with repeat indices 0, 1, 2
- [x] 1.3 Keep the retry policy inside a repeat; verify a retried timeout is recorded as one repeat, not two, and `repeat_count` still equals the configured k
- [x] 1.4 Verify one failed repeat does not stop the others for the same pair, and that each repeat is classified on its own outcome
- [x] 1.5 Add `--repeats` to the run command, defaulting to 1; verify the default produces one attempt per pair and the resolved count appears in the summary

## 2. Stability statistics

- [x] 2.1 Compute mean, min, max and standard deviation of the composite over scored repeats, per model; verify against a hand-computed fixture
- [x] 2.2 Compute the same per spec, so an unstable spec is visible; verify a spec with one wild repeat is flagged in the per-spec view
- [x] 2.3 Verify a pair with fewer than two scored repeats reports its spread as **not measured**, not as zero
- [x] 2.4 Compute the same per dimension; verify whether composite variance is dominated by `semantic` and record what you find
- [x] 2.5 Verify the statistics exclude infrastructure failures and match a hand recomputation over scored repeats only

## 3. Variance guard

- [x] 3.1 Mark a run `unstable` when a model's composite standard deviation exceeds the configured threshold; verify with fixtures above and below 0.05
- [x] 3.2 Name the affected models and state the threshold and the 2×sd interpretation rule in the flag; verify the wording appears in results and report
- [x] 3.3 Verify the guard is independent of the degenerate and exclusion-rate guards: construct a run that is unstable but neither of the others, and one that is each of the others but not unstable
- [x] 3.4 Verify an unstable run still writes its results and still exits non-zero
- [x] 3.5 Record the threshold and the interpretation rule in run metadata so a later run is judged against the rule that existed when it was made

## 4. Logging

- [x] 4.1 Emit one summary line per model at the end of a default run (mean, sd, widest spec sd, n, scored, excluded, repeats); verify a default run prints no per-attempt lines
- [x] 4.2 Add `-v/--verbose` showing one line per attempt with model, spec, repeat index, outcome, composite and elapsed time; verify the summary is unchanged by the flag
- [x] 4.3 Emit exactly one line per guard that fires, naming the guard, the model, the observed value and the threshold; verify each guard produces one line and no more
- [x] 4.4 Verify the tail of a default run's log answers: which models ran, each mean and spread, and whether any guard fired

## 5. Control model

- [x] 5.1 Add `opencode-go/qwen3.8-flash` as the control model in the comparison bank; verify it runs cleanly (no `provider_error`/`timeout`) and is identifiable in results as a control rather than a ranked peer
- [x] 5.2 State in the report which of the two control outcomes occurred: the control was separated, or it was not; verify both wordings exist and the correct one renders
- [x] 5.3 Verify a run with no control model states that the corpus's ability to discriminate was not measured, rather than omitting the question
- [x] 5.4 Verify the control is reported as a control and never presented as a ranked peer

## 6. Naming honesty

- [x] 6.1 Verify no data field, CLI output or report uses the term `pass@k`; confirm the wording is repeat stability / spread throughout
- [x] 6.2 Verify the report states that the figure measures repeatability, not eventual success

## 7. Measure, then decide

- [x] 7.1 Run the five models (four existing plus the control) over the full corpus at k=3; verify the run completes, logs read cleanly, and the schema and guards behave
- [x] 7.2 Record each model's mean and standard deviation, and apply the pre-registered rule from the design: state plainly whether the 0.063 spread clears 2×sd, and therefore whether any ordering is reportable
- [x] 7.3 Record whether the control model was separated from the others, and therefore whether the corpus can discriminate at all
- [x] 7.4 Record the per-dimension spreads, and state whether composite variance is dominated by the judge's opinion
- [x] 7.5 Record the observed exclusion rate and whether any guard fired; verify the run is not marked unstable, unreliable or inconclusive, or state which fired and why
- [x] 7.6 Update `docs/scoring.md` (variance, the guard, the naming distinction), `docs/report.md` (stability section) and `docs/roadmap.md` (move pass@k out of planned); verify every claim matches observed behaviour
- [x] 7.7 Write down the decision this measurement licenses: whether to add harder specs, add more models, or leave the corpus as is — as an explicit next step rather than a vague intention

## 8. Recorded result of the first k=3 measurement (2026-10-04)

Run: `reports/results-live20-v4.json`, schema 4, 300/300 attempts scored, 0 excluded,
no guard fired (not unstable, unreliable or inconclusive), 144 min.

| model | mean | sd | maxspec_sd |
| --- | --- | --- | --- |
| `deepseek-v4.1-flash` | 0.949 | 0.008 | 0.040 |
| `mimo-v2.6-flash` | 0.948 | 0.016 | 0.041 |
| `longcat-2.5-preview-free` | 0.927 | 0.010 | 0.060 |
| `deepseek-v4-pro` | 0.926 | 0.026 | 0.359 |
| **`qwen3.8-flash` (control)** | **0.927** | 0.025 | 0.232 |

**Spread = 0.023**, and the top two models are within 0.002 — far inside 2×sd. **No
ordering is reportable.** The 0.063 spread of the single-sample v3 run was one
noisy draw.

**The control was NOT separated** (gap 0.011, inside both floors). The corpus cannot
discriminate a deliberately weak small model from three pro models, so **the model
bank is not the limiting factor: the corpus is too easy.** Adding harder specs is
the licensed next step; adding more models is not.

**Tier ordering became monotonic** under k=3 (easy 0.950 > medium 0.942 > hard 0.929),
where the single-sample run had hard *above* medium. The ordering was noise before.

**Variance is not dominated by the judge.** sd(execution) = sd(edge) = 0.009;
sd(semantic) = 0.037, sd(style) = 0.041. But the largest single swing is genuine
code variation, not opinion: `deepseek-v4-pro` on `expression_evaluator` passed
**0/6 tests on repeat 0 and 6/6 on repeats 1 and 2** (composite 0.16 vs 0.93). A
single sample of that pair would have been a coin flip.

**Reference baseline unchanged:** execution 1.0, edge 1.0, style 0.598 — the
long-standing style ceiling is still the binding constraint on the composite.

**Licensed next step:** add harder specs (the control proves the corpus is the
limit), and treat the composite as a ceiling-limited figure given the 0.598 style
baseline.
