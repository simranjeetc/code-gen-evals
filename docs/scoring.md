# Scoring

Four dimensions are scored independently for every `(model, spec)` pair. They are
never averaged together before the fact — the whole point is to see where they
disagree.

| Dimension | Question it answers | Source of truth |
| --- | --- | --- |
| `execution` | Does the code pass the tests we wrote? | hidden ground-truth pytest suite |
| `edge` | Does it survive inputs the model never saw? | hidden edge-case pytest suite |
| `semantic` | Does it do what was actually asked? | an independent judge model |
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

### semantic

An independent judge model receives the requirement and the candidate and returns
`{"score": <0..1>, "rationale": "<...>"}`. The rubric tells it to judge intent
only and to ignore style.

Two rules are structural:

- **The judge must differ from the subject.** Asking a model to grade its own
  output is self-preference bias by construction; `ProviderJudge` refuses and
  abstains.
- **An unparseable judge response is an abstention**, recorded as `null`, not as
  `0`. It is excluded from semantic averages and counted in
  `semantic_abstentions`.

`0.0` without consulting the judge when no code was produced.

### composite

```
composite = Σ(weight_d × score_d) / Σ(weight_d)   over dimensions where score_d is not None
```

Default weights: `execution` 0.4, `edge` 0.25, `semantic` 0.25, `style` 0.1.
Configurable with `--weights execution=0.5,style=0.2`.

Weights are **renormalised over available dimensions**, so a judge abstention does
not silently become a zero. The trade-off is that two runs with different
abstention counts are only loosely comparable on composite — read the per-dimension
numbers when that matters.

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

The two are independent: a run can be unreliable without being degenerate, and
degenerate without being unreliable. They are reported as different conditions
because they call for different fixes.

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
- **A judge abstention changes the composite.** Renormalisation avoids punishing
  the model, but it does mean composite comparisons across runs with different
  abstention rates are approximate.
- **Excluding failures can flatter a flaky model.** The exclusion count is always
  reported and the exclusion-rate guard fires when the rate is material, but a
  run whose infrastructure is unstable is a weaker basis for a ranking than one
  that completed cleanly.
- **Schema version 2 is not comparable with version 1.** Older results scored
  infrastructure failures as `0.0`; new results exclude them. The report footer
  marks a stale file, but the numbers themselves do not mix.
