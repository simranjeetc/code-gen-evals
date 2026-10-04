# Scoring

Four dimensions are scored independently for every `(model, spec)` pair. They are
never averaged together before the fact — the whole point is to see where they
disagree.

| Dimension | Question it answers | Source of truth |
| --- | --- | --- |
| `execution` | Does the code pass the tests we wrote? | hidden ground-truth pytest suite |
| `edge` | Does it survive inputs the model never saw? | hidden edge-case pytest suite |
| `semantic` | Does it do what was actually asked? | an independent, reference-anchored judge model |
| `style` | Is it idiomatic, typed, readable Python? | deterministic static analysis |

All four are in `[0.0, 1.0]`.

## Formula reference

### execution

```
execution = passed(ground_truth tests) / total(ground_truth tests)
```

`0.0` when nothing ran, the run timed out, or the candidate crashed — a
**scored** result, because the harness worked and the candidate's code did not.
A response that could not be turned into code is not scored here at all; it is
classified `unparseable_output` and excluded (see *Attempt outcomes* in
`docs/execution.md`).

### edge

```
edge = passed(edge_case tests) / total(edge_case tests)
```

Computed from a *separate* execution against the hidden edge suite, so it is
independent of `execution`. A candidate can pass every visible test and still
score `0.0` here.

### style

Weighted average of independent checks, each in `[0, 1]`:

| Check | Weight | Passes when |
| --- | --- | --- |
| `parseable` | 0.10 | the source parses |
| `annotations` | 0.25 | every public function is fully annotated |
| `docstrings` | 0.15 | every public function has a docstring |
| `naming` | 0.15 | public function names are snake_case |
| `line_length` | 0.15 | every line is ≤ 100 characters |
| `complexity` | 0.10 | max cyclomatic complexity ≤ 10 |
| `bare_except` | 0.10 | no bare `except:` |

`annotations`, `docstrings`, and `naming` are fractional, so 2 of 4 annotated
functions scores `0.5` for that check. The per-check outcomes are stored with
each result, so a low style score is always explainable.

A source that does not parse scores `0.0` outright.

`ruff` is **opt-in** and only used when it is already on `PATH`. It is off by
default because enabling it would make style scores depend on what happens to be
installed, which breaks comparability across machines. When enabled, the final
score is `0.8 * core + 0.2 * ruff_clean`.

#### Finding: the reference solutions score 0.60 on style

Scored on its own accepted answers, the style dimension returns a mean of
**0.60** across the 20 references, and **none of the 20 reaches 0.99**. The style
checks are not calibrated against a neutral notion of quality: they reward
annotations and docstrings, and the references are deliberately minimal prose-free
solutions, so the accepted answer to every task loses roughly 0.4 to the house
style. This is a fact about the dimension, not a broken reference — `execution`
and `edge` are `1.0` for every reference.

Two consequences fall out of it:

- `style` should be read as "conforms to these specific heuristics", never as
  "quality".
- Because `style` carries weight `0.2`, the composite ceiling for
  reference-quality code is about `0.92` (`1.0×0.5 + 1.0×0.3 + 0.60×0.2`), not
  `1.0`. A composite near the top of the range is not evidence of a perfect
  solution.

### semantic

An independent judge model receives the **requirement**, the **reference
solution**, and the candidate, and returns
`{"score": <0..1>, "rationale": "<...>"}`. The rubric tells it to compare the
candidate against the reference — to judge intent only and to ignore style. The
reference anchors the scale: an absolute rubric makes the judge invent a standard
on every call, which is drift, and pairwise benchmarks (MT-Bench, AlpacaEval)
dominate precisely because a reference removes that freedom. The reference is
hidden from the model under test, so showing it to the judge leaks nothing to the
subject.

The prompt also carries a worked ladder — a concrete 1.0 / 0.5 / 0.0 — so the
bands are defined rather than inferred, and an explicit warning that a candidate
resembling the reference in shape but not behaviour must not score 1.0.

Structural rules:

- **The judge must differ from the subject.** Asking a model to grade its own
  output is self-preference bias by construction; `ProviderJudge` refuses and
  abstains.
- **An unparseable judge response is an abstention**, recorded as `null`, not as
  `0`. It is excluded from semantic averages and counted in
  `semantic_abstentions`.
- **The score is marked judge-derived** (`semantic_derived`) in the result schema,
  so no consumer can mistake the opinion for a measurement.

`0.0` without consulting the judge when no code was produced.

#### Judge agreement

Two different judge models score the same reference solutions via

```
.venv/bin/python -m codegen_evals.cli judge-agreement --out reports/judge-agreement.json
```

and the figure (exact-match rate and mean absolute difference) is recorded with a
run through `run --judge-agreement reports/judge-agreement.json`. This measures
**stability, not correctness**: two judges from the same vendor can share a bias
and agree. Human agreement is the only thing that validates correctness, and it is
not measured here.

##### The measured figure, and why it should not be over-read

`glm-5.3-flash` and `deepseek-v4.1-flash` scored all 20 reference solutions
identically: **exact-match rate 1.00, mean absolute difference 0.000**. That is a
real measurement, not a degenerate prompt — asked to score a deliberately empty
candidate, both judges returned `0.0` on the specs checked, so the scale moves.
But a 100% figure over 20 hand-written references is easy to over-read:

- The references are the *standard the prompt hands the judge*. Agreeing that the
  standard is the standard is near-tautological. This is the **most favourable
  possible input**, not an estimate of agreement on contested model output.
- The judges were run at the default temperature; a deterministic decode will
  agree more often than the deployed sampling.
- One judge abstained (`None`) on one wrong-candidate probe, so the pair is not
  perfectly reliable even on a non-reference input.

Read the figure as "these two judges do not disagree on the easy case", not as
"semantic scores are trustworthy".

##### Validation against the previous design

The four-model sweep was re-run under reference-anchored judging and the
objective-only composite (schema 3), and compared against the schema-2 run:

- **The run completed and is not inconclusive.** All 80 attempts scored; no model
  was flagged unreliable. Objective composite spread **0.063**.
- **Semantic moved in the direction the design predicted, slightly.** Over the 61
  pairs where both runs produced a semantic score, the mean fell from **1.000** to
  **0.967** (`−0.033`): 56 unchanged, 5 lower, none higher. The largest single drop
  was `−0.50`. Being shown the reference makes the judge harder to satisfy, which is
  the intended correction to an absolute rubric that had been drifting high — but
  the effect is small and this is one sample.
- **Abstentions rose, and the cause is the judge provider, not the prompt.** New
  13/80 versus old 8/80; see *Abstentions are judge provider failures* below. The
  probe shows the same prompt returning a timeout on one call and `1.0` on the
  next.

The composite is **not** compared across the two runs: it now covers different
dimensions, so a difference would be uninterpretable.

##### Abstentions are judge provider failures, not score-parse failures

In the validation run (4 models × 20 specs, schema 3), **13 of 80** semantic
scores abstained. That is a rise from 8 of 80 under the absolute-judging design,
and it would be easy to blame on the longer, reference-carrying prompt. It is not.
Probing the judge directly on a spec that abstained (`lru_cache`) with the *same*
reference-anchored prompt: one call returned `ProviderTimeout` and the next
returned `1.0`. The abstentions are judge **provider timeouts**, which fluctuate
run to run — not a systematic parse failure caused by the new rubric.

This matters for reading the semantic column: a `—` means "the judge did not
answer", which is an honest abstention, but its *frequency* is a harness property,
not a property of the candidate. Judge-provider reliability is not yet measured as
a disclosure figure; only judge-vs-judge agreement is.

### composite

```
composite = Σ(weight_d × score_d) / Σ(weight_d)   over objective dimensions where score_d is not None
```

Default weights: `execution` 0.5, `edge` 0.3, `style` 0.2. Configurable with
`--weights execution=0.5,style=0.2`.

`semantic` is **not** in the composite, even if a weight is supplied for it. It is
a judge's opinion; blending an opinion into a measurement at any weight is the
defect this design removes. The composite therefore answers "does it work, survive,
and read well" — not "does it do what was asked". Read the `semantic` column for
that, as an opinion. Weights are renormalised over the available objective
dimensions.

## Aggregation

Results are aggregated three ways, because a single average hides the interesting
structure:

- **by model** — per-dimension means and an overall composite
- **by model × tier** — is the model fine on `easy` and lost on `hard`?
- **by model × task type** — is it good at parsing and bad at concurrency?

Task-type tags come from each spec.

Every aggregate is computed over **scored attempts only**. An infrastructure
failure (provider timeout, provider error, unparseable output, or an attempt
that never ran) is excluded rather than averaged in as `0.0`. Each aggregate
reports the number of attempts it is based on (`n`) and the count of excluded
attempts (`excluded`), so a model is never credited or penalised for the harness
failing.

Two different exclusions are counted separately, because they mean different
things:

- **infrastructure exclusions** — the attempt was not a measurement (`excluded`,
  broken down by outcome);
- **semantic abstentions** — the attempt scored, but no judge opinion exists
  (`semantic_abstentions`).

A model with a high exclusion rate is **flagged, not rewarded**: its `excluded`
count is always shown, and the exclusion-rate guard below fires when the rate is
material.

## Exclusion-rate guard

Separate from the degenerate guard. When a model's share of infrastructure
failures exceeds `DEFAULT_EXCLUSION_RATE_THRESHOLD` (default 0.2), the run is
marked **unreliable** and the affected models are named. Results are still
written, and the CLI exits non-zero.

| guard | catches |
| --- | --- |
| degenerate | every model scored identically — the corpus measured nothing |
| exclusion-rate | too many attempts were not measurements at all |
| variance | a model's own score is not repeatable, so a gap to another model is not readable |

The three are independent: a run can be unreliable without being degenerate, and
vice versa. They are reported as different conditions because they call for
different fixes.

The defect this exists to catch is concrete. A four-model run over the corpus
reported a composite spread of `0.110` while three of eighty attempts were
infrastructure failures scored as `0.0`. Excluding those three by hand
collapsed the spread to `0.034` — the tie was never broken; the harness failure
was the "finding".

### Observed in practice

Under this change, a fresh four-model run over the same corpus recorded:

- **80 of 80 attempts scored; 0 excluded.** No model was flagged unreliable.
- The three attempts that had been infrastructure failures (two timeouts and one
  non-zero exit, all at the old 180s timeout) completed on the first attempt
  under the raised 300s timeout — the value used was `300s`.
- Four *different* transient failures were retried once and recovered
  (`csv_parse_line`, `lru_cache`, `retry_with_backoff`, `word_freq`); `retry_count`
  in the results file records which.
- The reported composite spread was **`0.016`**, against the old hand-corrected
  `0.034` and the old uncorrected `0.110`.

`0.016` does **not** equal `0.034`, and the model ordering changed. That is not a
regression in the accounting: a fresh run is a different sample, and 46 of the 80
`(model, spec)` composites moved between the two runs — several by more than
`0.3` on unrelated specs. The `0.034` figure was itself a single noisy sample. The
fix removes the mechanism that inflated the spread from failures-as-zeros; it does
not make the residual spread stable, because the corpus still does not reliably
separate these models.

## Disagreements

Detected per `(model, spec)` with thresholds `high` (default 0.8) and `low`
(default 0.6):

| Kind | Condition | What it means |
| --- | --- | --- |
| `tests_pass_semantics_fail` | execution ≥ high and semantic < low | passes the tests, misses the point |
| `passes_visible_fails_edges` | execution ≥ high and edge < low | works for the obvious case only |
| `correct_but_unidiomatic` | execution ≥ high and semantic ≥ high and style < low | right behaviour, poor code |

Each disagreement records the dimensions involved and the evidence behind it,
including which style checks failed.

## Repeat stability

Every `(model, spec)` pair is attempted `--repeats k` times (default 1). Each
attempt is an independent generation and execution and carries a `repeat` index;
a retry of a transient failure stays *inside* its repeat, so a flaky provider
cannot inflate the sample.

The spread of a pair's composites is **repeat stability**. It answers "how much
does this model wobble on this task", which is the noise a gap between two models
must clear to be reportable. It is computed **within a pair** — pooling different
specs would report how different the specs are, not how repeatable the model is.

- **per model:** `sd` is the mean per-spec sd (the noise), `spec_sd` is the widest
  single spec, `mean`/`range` are within-pair. Reported in `## Repeat stability`.
- **per spec:** a spec that swings by ≥ 0.20 across repeats is listed as a
  candidate ambiguous or flaky task, distinct from a genuinely hard one.
- **a pair with fewer than two scored repeats is reported `not measured`, never
  `0.00`.** A zero would look like *evidence* of stability; it is absence of
  evidence, the same defect class as a failure scored as zero.

### The variance guard

When a model's `sd` exceeds `VARIANCE_THRESHOLD` (default 0.05), the run is marked
**unstable** and the model is named. The rule states that a gap smaller than
`INSTABILITY_MULTIPLIER × sd` (default `2 × sd`) is not distinguishable from
run-to-run noise. The threshold and the rule are written into the run metadata, so
a later run is judged against the rule that existed when it was made rather than
one invented afterwards.

**Not `pass@k`.** This measures repeatability, not how often the model eventually
succeeds. `pass@k` ("passed at least once in k tries") is a generosity measure and
is deliberately absent from the data, the CLI and the report.

### The control model

A deliberately weak control (`--control-model`, suggested
`opencode-go/qwen3.8-flash`) is included so the corpus's ability to discriminate
is **measured, not assumed**. The report states which outcome occurred:

- **separated** — the control scored a material step below the subjects: the corpus
  discriminates, and a narrow spread among the remaining models is a property of
  the bank.
- **not separated** — the corpus cannot discriminate at all; the model bank is not
  the limiting factor and harder specs are the fix.
- **absent** — the report says the corpus's ability to discriminate was not
  measured, rather than staying silent.

The control is a control, never a ranked peer.

## Degenerate-run guard

If **every model scores identically on every dimension for every spec**, the run
is marked `inconclusive`, the results file is still written, and the CLI exits
non-zero.

This exists because "all 100%" and "all 0%" are the two ways a benchmark lies: in
both cases the corpus failed to measure anything, and reporting a ranking from it
would be fabrication. The reason string distinguishes all-perfect, all-zero, and
identical-but-middling.

## Limitations

- **Tests only assert what they assert.** A green execution score means "passed
  the cases we thought of", not "correct". The edge suite widens that a little; it
  does not close it.
- **LLM judges carry bias.** Self-preference is blocked by construction, but
  verbosity preference, position sensitivity, and cross-run drift are not.
  Rationales are stored so a human can audit the calls that matter.
- **Style checks are heuristics, not taste.** They reward annotations and
  docstrings. A model can score well by decorating mediocre code, and a model
  writing terse-but-clear code will be penalised. The reference solutions in this
  corpus are deliberately minimal, so reference-derived code lands mid-range.
- **The edge suite is finite.** "Handles edge cases" means "handles the edge cases
  we enumerated".
- **Composites are a convenience, not a verdict.** Weights are a judgement call;
  different weights reorder models. Read the dimensions.
- **The composite is deliberately narrower now.** It covers `execution`, `edge`
  and `style`, so it says "does it work, survive, and read well", not "does it do
  what was asked". That coverage loss is the price of keeping an opinion out of a
  measurement.
- **Judge drift is reduced, not eliminated.** Anchoring to the reference pins the
  scale down, but run-to-run variance remains. Rationales are stored so calls can
  be audited.
- **Two-judge agreement is stability, not validation.** Two judges can share a
  bias and agree; only human agreement validates correctness, and it is not
  measured here.
- **Excluding failures can flatter a flaky model.** The exclusion count is always
  reported and the exclusion-rate guard fires when the rate is material, but a
  run whose infrastructure is unstable is a weaker basis for a ranking than one
  that completed cleanly.
- **Schema version 3 is not comparable with earlier versions.** Version 2 scored
  infrastructure failures as `0.0`; versions before 3 asked the judge for an
  absolute score and blended it into the composite at weight 0.25. The report
  marks a historical file and says why.
