# Tasks

## 1. Project scaffold and packaging

- [x] 1.1 Create `pyproject.toml` declaring the `codegen-evals` package, Python `>=3.9`, and `pytest` as the only runtime/dev dependency; verify `pip install -e .` succeeds and `python -c "import codegen_evals"` works
- [x] 1.2 Create the `codegen_evals/` package skeleton (`cli.py`, `corpus.py`, `execution.py`, `reporting.py`, `providers/`, `scoring/`) with `from __future__ import annotations` in every module; verify each module imports without side effects
- [x] 1.3 Add `.gitignore` covering `.venv/`, `__pycache__/`, `.pytest_cache/`, `reports/*.json`, and `.opencode/cache`; verify `git status` stays clean after a test run
- [x] 1.4 Define the shared dataclasses (`Spec`, `Generation`, `ExecutionEvidence`, `DimensionScores`, `EvalResult`) with a `to_dict`/`from_dict` pair and a `SCHEMA_VERSION` constant; verify tests round-trip each dataclass through dict and back
- [x] 1.5 Add `.opencode/agents/codegen-eval.md` (tools denied, temperature 0) and `.opencode/agents/codegen-judge.md` (tools denied, judge rubric); verify `opencode run --agent codegen-eval --model opencode-go/mimo-v2.6-flash "Define add(a,b)."` returns a fenced block with no tool calls
- [x] 1.6 Write `docs/setup.md` describing install and the no-credential quickstart path; verify the documented commands run as written on a clean checkout

## 2. Corpus: spec format and the 15 specs

- [x] 2.1 Implement `corpus.py`: load specs from `corpus/<id>/spec.json`, validate required fields, tier values, and id uniqueness, and expose prompt rendering; verify unit tests cover a valid spec, a missing field, a bad tier, and a duplicate id
- [x] 2.2 Author the 5 easy specs (`fizzbuzz`, `word_freq`, `is_palindrome`, `chunk_list`, `parse_duration`) with `spec.json`, `solution.py`, `test_ground_truth.py`, and `test_edge_cases.py`; verify each reference passes both suites
- [x] 2.3 Author the 5 medium specs (`flatten_nested`, `lru_cache`, `merge_intervals`, `topological_sort`, `csv_parse_line`) with all four files; verify each reference passes both suites
- [x] 2.4 Author the 5 hard specs (`json_diff`, `rate_limiter`, `retry_with_backoff`, `thread_safe_counter`, `expression_evaluator`) with all four files; verify each reference passes both suites
- [x] 2.5 Tag every spec with task-type tags (e.g. `parsing`, `algorithms`, `data-structures`, `concurrency`, `error-handling`, `time`) and tier metadata; verify `list-specs` prints all 15 with tier and tags
- [x] 2.6 Implement corpus self-validation (run each reference against both suites) and expose it for the CLI; verify it reports all 15 specs sound, and fails loudly when a spec's reference is deliberately broken
- [x] 2.7 Add a test asserting prompt isolation: no rendered prompt contains reference source, test assertions, or edge-case test ids
- [x] 2.8 Write `docs/corpus.md` documenting `spec.json` fields, the tier scheme, the tag vocabulary, and how to add a spec; verify the documented "add a spec" steps produce a spec that passes validation

## 3. Model providers

- [x] 3.1 Implement the provider base contract (`generate(prompt, model_id) -> Generation`) with error capture and metadata; verify unit tests cover success and raised-exception paths
- [x] 3.2 Implement code extraction (first fenced `python`/`py` block, with bare-fence fallback) and extraction-failure handling; verify unit tests cover fenced, bare-fence, multi-block, and no-block responses
- [x] 3.3 Implement the deterministic mock provider driven by a per-(model, spec) fixture table; verify two invocations with the same input are byte-identical and that a full corpus run yields non-uniform scores
- [x] 3.4 Implement the OpenCode provider invoking `opencode run --agent codegen-eval --model <id> --format json` as a subprocess with a timeout, parsing NDJSON `text` parts; verify a live call to one `opencode-go` model returns extractable code and records duration
- [x] 3.5 Implement public-API adapters (Anthropic, OpenAI, Together/Llama) over `urllib.request` with stdlib JSON, reading keys from environment; verify each raises a clear named-credential error when its key is absent
- [x] 3.6 Add provider selection, the default model bank, temperature, and concurrency settings to config; verify a run over a two-model bank produces results for both
- [x] 3.7 Write `docs/providers.md` documenting provider selection, credentials, the OpenCode agent setup, and how to add a provider; verify the documented example produces a code block

## 4. Code execution

- [x] 4.1 Implement temp-dir + subprocess execution that writes candidate code to the spec's entrypoint module and copies the suite files in; verify a correct candidate produces a passing JUnit XML
- [x] 4.2 Implement JUnit XML parsing into per-test pass/fail evidence via `xml.etree.ElementTree`; verify unit tests cover all-pass, partial-fail, error, and skipped cases
- [x] 4.3 Enforce `subprocess.run(timeout=...)` and record timeout, non-zero exit, and crash as structured failures; verify a deliberately infinite-loop candidate is recorded as a timeout without hanging the suite
- [x] 4.4 Run ground-truth and edge suites as separate executions and merge their evidence; verify tests assert distinct evidence objects per suite
- [x] 4.5 Verify fault containment: a candidate that fails to import does not prevent later candidates from being evaluated
- [x] 4.6 Write `docs/execution.md` documenting the isolation model, timeout, and the explicit non-goal of adversarial sandboxing; verify the documented run command behaves as described

## 5. Scoring

- [x] 5.1 Implement execution and edge scores as passed-test fractions with zero-on-extraction-failure; verify unit tests cover full, partial, zero, and extraction-failure cases
- [x] 5.2 Implement the deterministic style analyzer (annotations, docstrings, snake_case, line length, complexity, bare except) with optional `ruff`; verify identical source scores identically twice and per-check outcomes are recorded
- [x] 5.3 Implement the semantic judge over the provider layer with a strict-JSON rubric, a judge model distinct from the subject, and `null` on unparseable output; verify tests cover a good score, a bad score, and an abstention
- [x] 5.4 Implement aggregation: per-dimension and composite scores by model, by tier, and by task type, with configurable weights; verify tests check a hand-computed aggregation
- [x] 5.5 Implement disagreement detection (green-tests/wrong-semantics, fragile-pass, correct-but-unidiomatic) with configurable thresholds; verify each class fires on a constructed fixture
- [x] 5.6 Implement the degenerate-run guard; verify a uniform-scores fixture is marked inconclusive and a differentiated fixture is not
- [x] 5.7 Write `docs/scoring.md` documenting each dimension's formula, weights, thresholds, and known limitations; verify every formula in the doc matches the implemented behavior

## 6. Reporting

- [x] 6.1 Implement results serialization with `SCHEMA_VERSION` and full run metadata; verify a results file round-trips and contains everything the report needs
- [x] 6.2 Implement the Markdown report: methodology, per-dimension explanation with limitations, metadata, model×dimension and model×tier tables, and overall ranking
- [x] 6.3 Implement the per-model strengths/weaknesses-by-task-type summary; verify it derives from spec tags and matches the computed scores
- [x] 6.4 Implement the disagreement section with model, spec, dimensions, and evidence; verify a run with planted disagreements renders them
- [x] 6.5 Verify the report renders from a stored results file with no network access
- [x] 6.6 Write `docs/report.md` explaining every report section and how to read it; verify the documented sections all appear in a generated report

## 7. CLI and pipeline

- [x] 7.1 Implement `list-specs`, `validate`, `run`, and `report` subcommands with `--specs`, `--tiers`, `--models`, `--provider`, `--weights`, `--out`, and `--json` options; verify `--help` lists all four commands and options
- [x] 7.2 Implement end-to-end `run` wiring corpus → providers → execution → scoring → disagreements → results file; verify a mock run over all 15 specs writes a complete results file
- [x] 7.3 Implement exit codes: non-zero on validation failure and on inconclusive runs, zero otherwise; verify each case with a targeted invocation
- [x] 7.4 Write the root `README.md` with the <5-minute quickstart, the `validate`/`run`/`report` flow, and an explanation of the four dimensions; verify the documented quickstart completes well under five minutes with no credentials
- [x] 7.5 Add a `Makefile` or documented one-liner for `make validate && make run-mock && make report`; verify it runs clean from a fresh checkout

## 8. Integration and acceptance

- [x] 8.1 Run `validate` and confirm all 15 specs report sound with references passing both suites
- [x] 8.2 Run the full mock pipeline end-to-end and confirm the produced report shows model differentiation (not uniformly 0 or 1) across dimensions and tiers
- [x] 8.3 Run a live OpenCode run over at least three `opencode-go` models on a subset of specs and confirm it completes, records per-call metadata, and produces a report with real (non-mock) differentiation
- [x] 8.4 Confirm the run duration for a 3-model × 15-spec pass is recorded and that setup-plus-quickstart stays under five minutes
- [x] 8.5 Review the generated report against the success criteria: ground truth per spec, per-method limitations documented, visible differentiation, and runnable end-to-end
