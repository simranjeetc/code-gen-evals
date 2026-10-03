# Execution

This is the layer that takes candidate code and a spec's suites and turns them
into structured pass/fail evidence.

## How a run works

For each (model, spec, suite) combination:

1. A fresh temporary directory is created.
2. The candidate code is written to `solution.py` in that directory.
3. The suite file (`test_ground_truth.py` or `test_edge_cases.py`) is copied in.
4. `python -m pytest <suite> --junitxml=report.xml -p no:cacheprovider -q` runs
   in a subprocess with `cwd` set to the temporary directory.
5. The JUnit XML is parsed into per-test evidence.
6. The temporary directory is deleted.

The suite imports the candidate with a plain `import solution`, which works
because pytest prepends the test file's directory to `sys.path`.

## Why JUnit XML

`--junitxml` is built into pytest. Parsing it with the standard library's
`xml.etree.ElementTree` means the framework needs no test-reporting plugin and
never scrapes human-readable output.

The parser records, per suite:

- `total` — number of test cases
- `passed` — test ids with no failure, error, or skip
- `failed` — test ids that failed, errored, or were skipped
- `messages` — the failure message for each non-passing test
- `duration_s`, `returncode`, `timed_out`, `setup_error`, `stderr_tail`

A test id looks like `test_ground_truth::test_scalar_replace`.

Skipped tests count as **not passed**. A skip is not evidence of correctness.

## Isolation model

- **Separate process** — a hung or crashing candidate cannot take down the run.
- **Temporary directory** — candidates cannot see or modify the corpus.
- **Hard timeout** — `subprocess.run(timeout=...)`, default 60s, enforced in
  Python because macOS has no `timeout` binary by default.
- **No network requirement** — suites are local; nothing is downloaded.
- **Fault containment** — a candidate that fails to import, crashes the
  interpreter, or times out is recorded as a structured failure and the next
  candidate is still evaluated.

## Attempt outcomes

A sandbox failure and a harness failure are not the same fact, and they are not
scored the same way. Every attempt carries an explicit `outcome`:

| Outcome | Meaning | Counts toward averages? |
| --- | --- | --- |
| `scored` | code was produced and run, whether or not it passed | yes |
| `timeout` | the **provider** exceeded its time budget | no — infrastructure |
| `provider_error` | the provider exited non-zero, errored, or refused a non-bare response | no — infrastructure |
| `unparseable_output` | the response contained no usable code block | no |
| `not_attempted` | the attempt was never made | no |

The decisive line is *whose fault it is*:

- A candidate that raises on import, loops forever, or prints the wrong answer
  is **`scored`**. The harness worked; the model's code did not. Its suite
  timeout is recorded as `timed_out` in the evidence and scores `0.0` on that
  dimension — correctly, because a hang is a model failure.
- A provider that times out or crashes, or a runner that cannot start, is an
  **infrastructure failure**. The model was never fairly tested, so it is
  excluded from every aggregate and listed under Reliability in the report.

Classification happens where the failure is observed — the provider boundary
(`ProviderError.outcome`, with `ProviderTimeout` for timeouts) and the execution
runner — not inferred downstream from a zero score.

## Retries and timeout

A `timeout` or `provider_error` is retried **once** at 1.5× the first budget
(`config.RETRY_TIMEOUT_MULTIPLIER`). An `unparseable_output` is not retried:
the model answered and the answer was unusable, so a second draw would record
luck as ability. Retries are bounded to two attempts total, so a permanently
failing attempt is recorded once and does not double the run's cost. A
successful retry is recorded as `scored` with `retry_count = 1`.

The default provider timeout is `config.DEFAULT_TIMEOUT_S` (300s). This was
raised from 180s, which was too tight for the largest hard specs: over the 77
successful calls in the run that exposed the defect, p95 was 69s and the maximum
was 130s. The value used for a run is recorded in its metadata.

## Reading the evidence

`ExecutionEvidence.fraction` is the passed-test fraction used directly as the
execution and edge-case dimension scores. It is `0.0` when no tests ran, which
is what a candidate timeout, import error, or collection failure produces — a
**scored** result: the model's code failed to run. A provider timeout never
reaches this layer; it is classified at the provider boundary and excluded.

## What this is *not*

This is **not an adversarial sandbox**. Model-authored code runs as your user on
your machine. There is no container, no seccomp filter, no filesystem jail
beyond the temp directory, and no egress blocking. A candidate that wanted to
delete your files could.

Treat a non-mock run as running untrusted code:

- Run it in a container or VM you are willing to lose.
- Do not point it at a working tree you care about.
- The mock provider does not execute model output and is safe by construction.

Container isolation is a deliberate non-goal for now; adding it is an opt-in
improvement, not a missing feature of the current design.
