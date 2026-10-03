# Corpus

The corpus is the fixed set of code-generation tasks every model is measured
against. It lives in `corpus/<spec-id>/`, one directory per task.

## Directory layout

```
corpus/<spec-id>/
  spec.json            # metadata + the prompt shown to the model
  solution.py          # reference solution (never shown to the model)
  test_ground_truth.py # hidden suite the model's code is judged on
  test_edge_cases.py   # hidden boundary/robustness suite
```

The model receives **only** the rendered prompt. The reference solution and
both suites are hidden. A test in `tests/test_corpus.py` enforces this by
asserting that no prompt contains test code, test names, or reference-solution
lines.

## `spec.json` fields

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Unique id; must equal the directory name |
| `title` | no | Human-readable name for the report |
| `tier` | yes | One of `easy`, `medium`, `hard` |
| `tags` | yes | Task-type tags, at least one (see below) |
| `prompt` | yes | The requirement shown to the model |
| `required_symbols` | yes | Public symbols the solution must define |

Both suites import the candidate as `solution`, so the entrypoint module name is
fixed at `solution`. A spec never needs to declare it.

## Tiers

- **easy** — one concept, single function, obvious control flow
- **medium** — needs a data structure, recursion, or a careful algorithm
- **hard** — multi-part specification, stateful classes, concurrency, or parsing

The corpus must contain at least 5 specs per tier; this is enforced by
`tests/test_corpus.py`.

## Tag vocabulary

Tags drive the "strengths and weaknesses by task type" section of the report.
Reuse existing tags where they fit; the current set is:

`algorithms`, `concurrency`, `control-flow`, `data-structures`, `decorators`,
`dicts`, `error-handling`, `graphs`, `iteration`, `lists`, `normalization`,
`numeric`, `parsing`, `recursion`, `sequences`, `sorting`, `state`,
`state-machine`, `strings`, `time`, `validation`

## How to add a spec

1. Create `corpus/<spec-id>/` with `spec.json`, `solution.py`,
   `test_ground_truth.py`, and `test_edge_cases.py`.
2. Keep the prompt to the requirement plus its deliverable contract. Do not
   restate the tests in prose and do not describe the reference implementation.
3. Give the hidden edge suite teeth: empty inputs, boundary values, error
   paths, and type extremes. This is where models separate.
4. Verify the spec end-to-end:

```bash
.venv/bin/python -m codegen_evals.cli validate
```

`validate` runs every reference solution against both of its suites and exits
non-zero if any spec is unsound, unavailable, or duplicated. A new spec is not
part of the corpus until this command passes.

5. Confirm the prompt leaks nothing:

```bash
.venv/bin/python -m pytest tests/test_corpus.py -q
```

## Why the suites are hidden

Ground-truth tests that the model can read become part of the prompt, and the
model then optimises for the assertions rather than the requirement. Keeping the
edge suite hidden is what makes the *edge-case handling* dimension measure
robustness rather than test-reading.

## Limitations

- 15 specs is a small sample. Per-spec results are reported alongside aggregates
  because a one-spec difference is noise.
- These are classic tasks, so training-data contamination is not controlled for.
  A model may have seen `fizzbuzz` many times over.
- Hidden suites are still finite. Passing every edge test means "no failure in
  the cases we thought of", not "correct".
