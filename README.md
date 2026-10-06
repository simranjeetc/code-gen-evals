# code-gen-evals

A four-dimension evaluation framework for code-generation model quality.

Most benchmarks answer one question — "did it pass the tests?" — and report a
single number. That number hides the cases that matter: code that passes the
tests but misses the point, code that works for the obvious case and breaks on the
edges, code that is correct and unreadable. This framework scores those separately
and reports where the dimensions disagree.

## The four dimensions

| Dimension | Question | Source of truth |
| --- | --- | --- |
| **execution** | Does it pass the tests we wrote? | hidden ground-truth pytest suite |
| **edge** | Does it survive inputs the model never saw? | hidden edge-case pytest suite |
| **semantic** | Does it do what was actually asked? | an independent judge model |
| **style** | Is it idiomatic, typed, readable Python? | deterministic static analysis |

Each is scored `0.0–1.0`, aggregated by model, by difficulty tier, and by task
type, with cross-dimension disagreements flagged explicitly.

## Quickstart (under five minutes, no credentials, no network)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"

.venv/bin/python -m codegen_evals.cli validate
.venv/bin/python -m codegen_evals.cli run --provider mock --out reports/results-mock.json
.venv/bin/python -m codegen_evals.cli report --in reports/results-mock.json --out reports/report-mock.md
```

The `pip install --upgrade pip` step is required: the pip bundled with the system
Python on macOS (21.x) predates PEP 660 and cannot install a `pyproject.toml`-only
project in editable mode.

Or the same thing in one step:

```bash
make quickstart
```

`validate` proves the corpus is sound by running every reference solution against
both of its suites. `run` scores the model bank and writes a results file plus a
Markdown report. The `mock` provider is deterministic and offline, so this works
on a fresh checkout with nothing configured.

**A mock run validates the pipeline; it is not a model comparison.** The mock
synthesises candidates from the reference solutions, and the report says so.

## Real models

Real runs reuse locally installed OpenCode models — no extra API keys:

```bash
.venv/bin/python -m codegen_evals.cli run --provider opencode --out reports/results.json
```

This requires the `opencode` CLI on `PATH` with an authenticated installation.
Generation is pinned to `.opencode/agents/codegen-eval.md`, which denies every tool
and sets `temperature: 0`, so a model produces a bare code block instead of acting
on the repository.

Hosted backends are supported when their credentials are present:
`--provider anthropic|openai|together` with `ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`, or `TOGETHER_API_KEY`. Selecting one without a credential fails
loudly, naming the variable.

> **Non-mock runs execute model-authored code on your machine.** The execution
> layer uses a temp directory and a hard timeout; it is not an adversarial
> sandbox. See [docs/execution.md](docs/execution.md).

## Commands

| Command | Purpose |
| --- | --- |
| `list-specs` | list the corpus with tiers and task-type tags |
| `validate` | run every reference against both suites; non-zero on any failure |
| `run` | evaluate models and write `results.json` + a report |
| `report` | re-render a report from a stored results file (offline) |
| `judge-agreement` | score the reference solutions with two judge models and measure their agreement |

Useful options: `--specs`, `--tiers`, `--models`, `--judge`, `--judge-agreement`,
`--weights`, `--repeats`, `--control-model`, `-v/--verbose`, `--concurrency`,
`--timeout`, `--suite-timeout`, `--exclusion-threshold`, `--ruff`, `--json`.

## Repository layout

```
corpus/<spec-id>/     spec.json + reference solution + hidden ground-truth and edge suites
codegen_evals/
  cli.py              command-line surface
  pipeline.py         corpus -> providers -> execution -> scoring orchestration
  corpus.py           spec loading, validation, prompt rendering, self-validation
  execution.py        temp-dir subprocess runs + JUnit XML evidence
  providers/          opencode (default), mock (offline), anthropic/openai/together
  scoring/            four dimensions, aggregation, disagreement detection
  reporting.py        Markdown report
openspec/             spec-driven change artifacts for this work
docs/                 setup, corpus, providers, execution, scoring, report
reports/              generated results and reports (gitignored)
```

## Documentation

- [docs/setup.md](docs/setup.md) — install, quickstart, credentials
- [docs/corpus.md](docs/corpus.md) — spec format, tiers, tags, how to add a spec
- [docs/providers.md](docs/providers.md) — backends, the OpenCode agent, extraction
- [docs/execution.md](docs/execution.md) — isolation model and its non-goals
- [docs/scoring.md](docs/scoring.md) — formulas, weights, thresholds, limitations
- [docs/report.md](docs/report.md) — how to read the report
- [docs/roadmap.md](docs/roadmap.md) — ideas with evidence, and what's been rejected
- [docs/decisions.md](docs/decisions.md) — every decision and why, the measurement log, and the lessons

## Known limitations

- **20 specs is a small sample**, and the original 15 are well-known tasks, so
  training-data contamination is not controlled for. Per-spec results are reported
  so a small aggregate gap can be checked.
- **Averages exclude infrastructure failures.** A provider timeout or crash is
  classified and excluded, never scored `0.0`; the report lists every exclusion
  and flags a run as unreliable when too many attempts were not measurements.
  Results before schema version 2 scored those failures as zeros and are not
  comparable with new runs.
- **The semantic dimension depends on an LLM judge.** It is anchored to the
  reference solution, marked judge-derived, and kept **out** of the composite; but
  it is still an opinion, and two-judge agreement measures stability, not
  correctness. Self-preference is blocked by requiring a different judge model.
- **Style checks are heuristics.** They reward annotations and docstrings outright.
- **Execution is not sandboxed.** Treat non-mock runs as running untrusted code.

Every eval method's limitations are documented in [docs/scoring.md](docs/scoring.md)
and repeated in the generated report.
