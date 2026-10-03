# Design

## Context

Greenfield repository. See `proposal.md` for motivation and `specs/*/spec.md` for requirements.

Constraints discovered while grounding this design on the target machine (macOS arm64, Python 3.9.6, OpenCode v2.0.19):

- No hosted-model credentials are available (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `TOGETHER_API_KEY` are all unset).
- An OpenCode subscription is available and already authenticated, exposing 29 models under the `opencode-go` provider. This is the practical model bank.
- A live OpenCode server is running; `opencode run --model <id> --format json` was verified to return a clean fenced code block in ~8s with no tool use when given a tools-disabled agent.
- The default bank was verified live, not assumed: `deepseek-v4-pro`, `deepseek-v4.1-flash`, `mimo-v2.6-flash`, and `longcat-2.5-preview-free` each returned extractable code, and the judge `glm-5.3-flash` returned strict JSON (`{"score": ..., "rationale": ...}`).
- Node/npm were absent, so the OpenSpec CLI was installed via Homebrew (`brew install node`, `npm i -g @fission-ai/openspec`, v1.14.0).
- Only the Python standard library and `pytest` may be assumed present.

## Goals / Non-Goals

**Goals:**

- One command produces a scored, disagreement-aware, human-readable report.
- Deterministic, offline, credential-free end-to-end run for CI and quickstart.
- Provider layer that can drive OpenCode models today and public APIs later without touching scoring.
- Scores that visibly separate models across tiers and task types.

**Non-Goals:**

- Adversarial or untrusted-code sandboxing (no containers, seccomp, or network egress control).
- Statistical significance testing or confidence intervals beyond per-spec granularity warnings.
- Training-data contamination control (models may have seen these classic tasks).
- A web UI, database, or long-running service.

## Decisions

### D1: Invoke OpenCode models through the CLI, not the HTTP server or SDK

Use `opencode run --agent codegen-eval --model <provider/model> --format json "<prompt>"` as a subprocess. Its NDJSON `text` parts are parsed for the code block.

- Why: verified working; the CLI carries existing authentication; no SDK install and no server auth token handling.
- Alternatives considered: the OpenCode HTTP/SDK API (rejected: extra auth surface, `/openapi.json` returns 401 without a token); direct provider HTTP calls (rejected: no credentials); `opencode api` (rejected: same auth surface, more brittle).

### D2: A dedicated project agent pins generation to a bare completion

`.opencode/agents/codegen-eval.md` sets `temperature: 0` and denies `read`, `edit`, `glob`, `grep`, `list`, `bash`, `task`, `webfetch`, `websearch`, and `todowrite`. Verified: the model answers with a single fenced block and invokes no tools.

- Why: the default agent is agentic and may write files or narrate, which pollutes the "code produced from a prompt" signal.
- Alternative considered: passing a system prompt per call (rejected: does not remove tool availability).

### D3: Four dimensions scored from independent evidence, never collapsed early

Execution = fraction of ground-truth tests passed; edge = fraction of hidden edge tests passed; style = deterministic static checks; semantic = a judge model's rubric score. Raw scores are kept per (model, spec) and only combined at the aggregation layer.

- Why: the product's whole value is exposing where dimensions disagree; early averaging destroys that.
- Alternative considered: a single weighted score as the primary output (rejected: hides disagreement, which is the point).

### D4: `pytest` with JUnit XML, parsed by stdlib

Run each suite in a subprocess as `python -m pytest --junitxml=<tmp>.xml -p no:cacheprovider`, then parse the XML with `xml.etree.ElementTree`.

- Why: `--junitxml` is built into pytest, so no `pytest-json-report` dependency and no fragile stdout scraping.
- Alternative considered: a custom pytest plugin writing JSON (rejected: more moving parts for the same result); parsing `-q` output (rejected: fragile).

### D5: Style is scored by stdlib AST + tokenize checks, with ruff opt-in

Checks include public-function annotations, docstrings, snake_case naming, line length, cyclomatic complexity, and bare `except`.

- Why: keeps the default install dependency-free and the score deterministic and explainable.
- `ruff` is only used when explicitly enabled and only when it is already on `PATH`. Auto-enabling it would make style scores non-comparable between machines, which defeats the point of a comparable benchmark.
- Alternative considered: making `ruff`/`radon` hard dependencies (rejected: heavier setup, and linter scores are not the same thing as a graded style signal).

### D6: The semantic judge is a different model, and its score is allowed to be abstained

Judge calls go through the same provider layer with a separate model id (default `opencode-go/glm-5.3-flash`, subject models are others). The judge returns strict JSON `{score, rationale}`. If the judge is unreachable or returns unparseable output, the semantic score is `null` and excluded from averages, with the abstention recorded.

- Why: avoids self-preference bias and avoids fabricating a semantic score from a failed judge call.
- Alternative considered: reusing the model under test as its own judge (rejected: self-preference); a rule-based semantic check (rejected: cannot judge intent).

### D7: Results are a versioned JSON artifact; the report is a pure function of it

`run` writes `results.json` with `schema_version` and full metadata; `report` reads only that file.

- Why: reporting is re-runnable and diffable without paying for another evaluation pass.
- Alternative considered: report generated inline during the run (rejected: couples the two and blocks re-rendering).

### D8: Degenerate runs are failures, not results

If every model scores identically on every dimension for every spec, the run is marked `inconclusive`, the results file is still written, and the process exits non-zero.

- Why: an all-pass or all-fail corpus is a corpus bug, and success criteria require visible differentiation.

### D9: Default model bank and weights

Bank (subjects, config-driven): `opencode-go/deepseek-v4-pro` (strong anchor), `opencode-go/deepseek-v4.1-flash`, `opencode-go/mimo-v2.6-flash`, and `opencode-go/longcat-2.5-preview-free` (zero-cost). Premium models are deliberately excluded from the default bank; a model is selected only by explicit config. Judge default is `opencode-go/glm-5.3-flash` and MUST NOT also appear as a subject. Composite weights default execution 0.4, edge 0.25, semantic 0.25, style 0.1; disagreement thresholds default high 0.8 / low 0.6. A 4-model × 15-spec run plus judge calls costs a few cents at list prices, with one subject free.

The strong anchor (`deepseek-v4-pro`) exists so a visible capability gap is likely before the dimension-level breakdown is even considered, while the other three cover the low-cost end. Differentiation is still expected to come primarily from the four dimensions and the tier × task-type breakdown rather than from overall level alone — models that tie overall often split on style versus edge-case handling. If the report nonetheless shows the bank indistinguishable, the corpus is under-powered for this bank and specs need hardening; the degenerate-run guard and the inconclusive exit code exist exactly for that case.

- Why: spans capability and cost tiers so differentiation is likely, while staying on the existing subscription.

### D10: Package layout keeps capabilities separable

```
corpus/<spec-id>/{spec.json, solution.py, test_ground_truth.py, test_edge_cases.py}
codegen_evals/
  cli.py            # eval-cli
  corpus.py         # spec-corpus
  providers/{base,mock,opencode,public_api}.py   # model-providers
  execution.py      # code-execution
  scoring/{dimensions,semantic,style,aggregate,disagreements}.py   # eval-scoring
  reporting.py      # eval-reporting
tests/              # framework unit tests
reports/            # generated output
```

- Why: each module maps to one capability, so specs stay independently changeable. The eval corpus lives in `corpus/` rather than `specs/` to avoid collision with `openspec/specs/`.

## Risks / Trade-offs

- [Generated code is executed on the host with no real sandbox] → Run only in a temp dir with a hard timeout and no network dependency; document loudly that non-mock providers execute model-authored code and should be reviewed; keep container isolation as a future opt-in.
- [`opencode run` spawns an agent, which may still narrate or use tools] → Dedicated tools-disabled agent plus strict output contract plus fenced-block extraction; a missing block is scored zero, not crashed on.
- [No credentials means the only guaranteed run is the mock provider] → Mock provider is deterministic and exercises the full pipeline; the report labels mock runs as pipeline validation, not a real ranking.
- [Mock differentiation is artificial] → Explicitly flagged in the report metadata and limitations; never presented as a model comparison.
- [LLM judge bias, verbosity sensitivity, and drift] → Judge differs from subject, rubric is fixed, rationale is recorded, score is bounded, and the limitation is written into the report.
- [15 specs is a small sample] → Report per-spec results alongside aggregates and warn that differences under one spec are noise.
- [macOS lacks `timeout`; subprocess timeouts must be enforced in Python] → Use `subprocess.run(timeout=...)` rather than a shell `timeout` binary.
- [Python 3.9 target limits syntax] → Use `from __future__ import annotations`; avoid 3.10+ union syntax at runtime.

## Migration Plan

Greenfield; no migration. Rollback is deleting the added files. The only host-level change is tooling installation (Node, OpenSpec) and the `.opencode/agents/` files, all of which are additive.

## Open Questions

None blocking. Corpus spec wording will be finalized during implementation against the corpus self-validation command.
