# Proposal

## Why

Teams pick code-generation models on vibes. Execution pass rates disagree with semantic correctness, and semantic correctness disagrees with idiom — so a single "it passed" number hides where a model actually fails. We need a repeatable framework that scores generated Python on four independent dimensions, makes those disagreements explicit, and reports model strengths and weaknesses by task type.

## What Changes

- Introduce a Python eval framework that runs a fixed corpus of code-generation specs against a configurable bank of models.
- Define four scoring dimensions: **execution** (does it pass the ground-truth pytest suite), **semantic** (does it satisfy the stated intent, judged independently of the tests), **style** (idiomatic, typed, readable Python), and **edge-case handling** (hidden boundary tests the model never sees).
- Ship a corpus of 15 specs across three difficulty tiers (5 easy / 5 medium / 5 hard), each with a reference solution and a passing ground-truth pytest suite, plus a hidden edge-case suite.
- Make models pluggable. Default bank uses the existing OpenCode Go subscription models (no extra API cost); `mock` provider makes the whole repo runnable offline; public-API adapters (Anthropic, OpenAI, Together for Llama) are supported when keys are present.
- Detect and flag cross-dimension disagreements (e.g. passes tests but violates intent; correct but unidiomatic; passes visible tests but breaks on edges).
- Emit a human-readable Markdown report: per-dimension and per-tier model matrices, strengths/weaknesses by task type, a disagreement section, and documented limitations for every eval method.
- Add a `validate` command that proves the corpus is sound by running each ground-truth solution against its own suites.

## Capabilities

### New Capabilities

- `spec-corpus`: defines the spec format, difficulty tiers, task-type tags, reference solutions, and hidden ground-truth/edge suites, plus corpus self-validation.
- `model-providers`: pluggable model invocation (OpenCode Go default, offline mock, public API adapters), prompt contract, and raw response capture.
- `code-execution`: isolates and runs candidate code against the ground-truth and edge suites, producing raw per-suite evidence.
- `eval-scoring`: turns raw evidence into the four dimension scores, aggregates by model/tier/task type, and detects cross-dimension disagreements.
- `eval-reporting`: renders a human-readable Markdown report with model comparisons, strengths/weaknesses, disagreements, and per-method limitations.
- `eval-cli`: the end-to-end pipeline and CLI that wires corpus, providers, execution, scoring, and reporting into one runnable command.

### Modified Capabilities

_None — greenfield repository._

## Impact

- New Python package `codegen_evals`, a `specs/` corpus directory, generated `reports/`, and tests.
- Runtime dependencies kept minimal (stdlib-first; pytest for suites). No hosted-model credentials required for a default run.
- Repository is greenfield; no existing code or APIs are affected.
- Deviation from the original brief: model comparison uses OpenCode Go models (reusing the existing subscription) instead of live Claude/GPT-4/Llama public APIs. Public-API adapters remain in scope but stay inactive until keys are supplied.
