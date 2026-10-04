# Report

The report is a pure function of a results file. Rendering it needs no network,
no models, and no re-run:

```bash
.venv/bin/python -m codegen_evals.cli report --in reports/results.json --out reports/report.md
```

Re-render after changing weights or thresholds to see how a different definition
of "good" reorders the models.

## Reading it, section by section

### Header

If the run is marked inconclusive, a warning appears immediately below the title.
That means the corpus did not differentiate the models — see
[Degenerate-run guard](scoring.md#degenerate-run-guard). Any ranking that follows
is meaningless, so stop reading.

If the run is marked **unreliable**, a separate warning names the affected models.
That means too many attempts were infrastructure failures rather than
measurements — see
[Exclusion-rate guard](scoring.md#exclusion-rate-guard). The scores are still
computed over scored attempts, but a flaky harness is a weak basis for a ranking.

### Run metadata

Everything needed to reproduce or judge the run: schema version, provider, the
exact model ids, the semantic judge and its design, the judge-agreement figure if
one was recorded, corpus size and tier counts, generation temperature, repeats per
pair, the control model if one was set, the variance guard's threshold and rule,
composite weights, disagreement thresholds, the provider timeout and exclusion-rate
threshold, and timestamps.

If the file predates reference-anchored judging, a banner marks it historical and
says why it is not comparable with new runs. Schema-3 files (one attempt per pair,
no repeat spread) are marked historical for the same reason.

If the provider is `mock`, a banner says so. **A mock run validates the pipeline;
it is not a model comparison.** The mock synthesises candidates from the reference
solutions, so its numbers describe the harness, not any real model.

### Method

The four dimensions, what each measures, and where its evidence comes from.
Followed by the limitations of each method — read this before quoting any number.

### Model comparison

One row per model: composite plus all four dimensions plus `n` (scored attempts
each average is based on) and `excl` (attempts excluded as infrastructure
failures).

The composite covers `execution`, `edge` and `style` only. `semantic` is a
judge's opinion, shown alongside but **excluded from the composite** — so the
composite tells you whether a model works, survives, and reads well, not whether
it does what was asked.

Read the *row*, not the composite. Two models can share a composite while one
wins on `execution` and the other on `edge` — that is the useful signal, and it is
why the dimensions are not collapsed earlier.

`semantic` shows `—` when the judge abstained for every spec for that model.

Directly under the table is the **judge-agreement** line. If two judges were
measured over the reference solutions, it reports how often they agreed exactly
and their mean absolute difference; if not, it says the figure is unmeasured. The
measurement is stability, not correctness — two judges can share a bias and agree.

### Repeat stability

Present when `--repeats` is greater than one. It reports, per model, the spread of
its own composite across repeats — `sd` (the mean per-spec run-to-run noise),
`widest spec sd`, and the mean within-spec range. This is the **noise a gap between
two models must clear**; a gap that does not exceed roughly `2 × sd` is not
reportable. The section then lists any spec that swung by ≥ 0.20 across repeats (a
candidate ambiguous or flaky task) and the per-dimension spreads.

It measures **repeatability, not eventual success** — it is not `pass@k`. A pair
with fewer than two repeats is reported `not measured`, never `0.00`.

If the run is **unstable** (a model's `sd` exceeds the threshold), the banner at the
top of the report says so and names the model.

### Control model (does the corpus discriminate?)

Present when a control model was set. It states plainly which outcome occurred: the
corpus **separated** the deliberately weak control (it discriminates — a narrow
spread among the rest is the bank), or it **did not** (the corpus cannot
discriminate — harder specs are the fix). With no control, the section says the
corpus's ability to discriminate was not measured. The control is marked
`_(control)_` in every table and is never ranked as a peer.

### Reference baseline

The task authors' accepted solutions scored on `execution`, `edge` and `style`.
This is the ceiling the models are measured against. `semantic` is omitted: the
reference *is* the standard, so judging it says nothing. A reference below `1.0`
on `style` is expected — the style checks reward annotations and docstrings, and
the references are deliberately minimal.

### Reliability

Infrastructure failures are listed here with their outcome and message, so they
are excluded from the tables but never hidden. Per model, the section shows
attempts, scored, excluded, and the exclusion rate — the denominator behind every
average. If the run is unreliable, the warning here is prominent and names the
models.

The distinction this section enforces: a provider timeout or crash means the
model was **not fairly tested**; a sandbox crash means the model wrote bad code
and is scored `0.0` on that dimension like any other wrong answer.

### Performance by difficulty tier

Model × tier, with the dimensions. This is where "fine on easy, lost on hard"
shows up. A model with a flat profile across tiers is consistent; a model that
collapses on `hard` is not ready for real work regardless of its composite.

### Strengths and weaknesses by task type

Per model, task types ordered best to worst, with the strongest and weakest called
out by name.

**Read the `n` column.** A task type is a bucket of specs sharing a tag, and many
buckets hold one or two specs. A difference in a one-spec bucket is noise. Only
trust a task-type finding that spans several specs.

### Disagreements

The reason four dimensions are reported instead of one. Each entry is a case where
the dimensions tell different stories:

- `tests_pass_semantics_fail` — passes the tests, misses the point
- `passes_visible_fails_edges` — works for the obvious case only
- `correct_but_unidiomatic` — right behaviour, poor code

Each entry names the model, the spec, the dimensions involved, the scalar evidence,
and (for style) which checks failed. Counts by kind appear above the detail.

A disagreement is a finding, not a defect. If nothing is flagged, either the models
are uniformly good, or the thresholds are loose — check the thresholds in the
metadata.

### Per-spec results

The raw table: every `(spec, model)` pair with all four scores and its disagreement
flags. An attempt that was an infrastructure failure is shown as
`_excluded (outcome)_` rather than a row of zeros, so a failure is never read as a
low score.

Absolute level matters here, but relative gaps do not: with 20 specs, a gap under
roughly 0.15 on a single spec is not meaningfully different. Use this section to
spot *systematic* patterns — the same model failing the same tier or tag — not to
rank individual specs.

### Reading this report

A short closing summary of the above, including the reminder that the composite is
a convenience with arbitrary weights.

## Limitations of the report itself

- It can only show what the corpus measured. 20 well-known specs are a small,
  contamination-prone sample.
- Task-type buckets are thin; most single-bucket differences are noise.
- The composite encodes a judgement (the weights). Different weights reorder
  models, which is why the dimensions are always shown alongside it.
- Semantic scores depend on an LLM judge; see
  [Scoring limitations](scoring.md#limitations).
