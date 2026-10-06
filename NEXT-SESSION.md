Continue work in /Users/simran/codebase/code-gen-evals.

Read these first, in this order:
1. docs/decisions.md — every decision, why, the measurement log, and the lessons
2. docs/roadmap.md — the "In flight" section: what is next and why
3. openspec/changes/add-harder-specs/ — the planned change (proposal, design, tasks)

## What the project is

A four-dimension eval framework for code-generation model quality. It scores
generated Python on execution (hidden ground-truth tests), edge (hidden edge-case
tests), semantic (a judge model), and style (deterministic static analysis), then
reports model strengths and weaknesses by tier and task type.

20 specs in `corpus/`, 5/5/10 across easy/medium/hard. Schema version 4.

## Where things stand (2026-10-06)

Three changes are **implemented, measured, synced and archived**:

- `separate-harness-failures` (schema 1→2) — a failure is classified, not scored zero
- `anchor-semantic-judge` (schema 2→3) — the judge is anchored; semantic is out of the composite
- `add-pass-at-k-variance` (schema 3→4) — repeats, spread, the variance guard, a control model

The k=3 measurement landed and it is the central finding:

- 300/300 attempts scored, 0 excluded. Spread **0.023**; top two within 0.002.
- The **control model was NOT separated** — a deliberately weak small model scored
  mid-pack. Per the pre-registered rule, **the corpus cannot discriminate; the
  model bank is not the limit.**
- 58 of 60 attempts pass every ground-truth test. The tests are too easy.

## What is next

**`add-harder-specs`** — planned, 4/4 artifacts, validated strict, not implemented.
10 original hard specs, corpus 20→30, with a pre-registered acceptance rule. Run
`/opsx apply add-harder-specs`.

The one-line reason: the previous change proved the corpus cannot rank models; this
one adds specs whose hidden tests actually fail a competent model.

## How to work in this repo

- Use OpenSpec. Run `/opsx apply <change-name>` and work the task list.
- Every task names how to verify it. Do the verification, don't assert it.
- Docs are tasks in the same group as the code, deliberately.
- **Maintain `docs/decisions.md`.** When a change is archived, add its decisions.
  When a measurement changes what is true, update the measurement log. When a
  defect repeats, add it to lessons. See the file's "How to maintain this".
- Run `.venv/bin/python -m pytest -q` before claiming anything is done. Baseline
  is **290 passed, 2 skipped**.
- Run `.venv/bin/python -m codegen_evals.cli validate` to check corpus soundness.
  Baseline is **20 specs, 40 suite runs, all sound**.

## Known environment facts, do not rediscover these

- Node and openspec are at `/opt/homebrew/bin` — it is NOT on the default PATH.
  Prefix with: `export PATH="/opt/homebrew/bin:$PATH"`
- The opencode CLI is at `/opt/homebrew/bin/opencode` and `~/.opencode/bin/opencode`
- The claude CLI is at `~/.local/bin/claude`. `which claude` fails because
  `~/.local/bin` is not on PATH. This is expected, not a fault.
- python3 is the system 3.9; the project venv is at `.venv/`
- If `git add` is blocked by permissions, retry with `/usr/bin/git`
- Long runs are quiet by default; they write the results file only at completion.
  Run them in the background and check the log tail.

## What I care about more than speed

1. If a result looks like a finding, check for an alternative explanation before
   reporting it. Every real bug here has been a failure that looked like a result.
2. If a change makes earlier numbers incomparable, say so plainly rather than
   quietly re-running. Every schema bump does exactly that.
3. Fix the accounting before changing what is accounted for.

## Current state

Everything committed, working tree clean. Baseline run:
`reports/results-live20-v4.json` (schema 4, 20 specs, k=3, 0 excluded).
All earlier `reports/*.json` are historical and not comparable.
