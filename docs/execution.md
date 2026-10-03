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

## Reading the evidence

`ExecutionEvidence.fraction` is the passed-test fraction used directly as the
execution and edge-case dimension scores. It is `0.0` when no tests ran, which
is what a timeout, import error, or collection failure produces.

Because extraction failures produce no code at all, they are scored `0.0` for
execution and edge without ever reaching this layer.
