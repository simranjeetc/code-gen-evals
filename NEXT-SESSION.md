Continue work in /Users/simran/codebase/code-gen-evals.

There are two OpenSpec changes ready to implement. Start with the first one.

Read these first, in this order:
1. docs/roadmap.md — the "In flight" section explains what is next and why
2. openspec/changes/separate-harness-failures/proposal.md and design.md
3. openspec/changes/anchor-semantic-judge/proposal.md and design.md

Then run /opsx apply separate-harness-failures

Do not start anchor-semantic-judge until separate-harness-failures is done. The
order matters: timeouts currently score as zeros, and changing the judge while
that is still true produces a different-shaped wrong answer. Fix the accounting
before changing what is being accounted for.

## What the project is

A four-dimension eval framework for code-generation model quality. It scores
generated Python on execution (hidden ground-truth tests), edge (hidden
edge-case tests), semantic (a judge model), and style (deterministic static
analysis), then reports model strengths and weaknesses by tier and task type and
flags cross-dimension disagreements.

20 specs in corpus/, 5/5/10 across easy/medium/hard. 5 models reachable: four via
the OpenCode subscription and one via Claude Code.

## What the two changes fix

Both are the same defect class: a failure rendered as a confident number.

separate-harness-failures — a provider timeout or crash is scored 0.0,
indistinguishable from a model that wrote bad code. This already produced one
false finding: a four-model run appeared to break the tie with a spread of 0.11,
which collapsed to 0.035 once three infrastructure failures were removed by
hand. The fix classifies every attempt, excludes infrastructure failures from
aggregates without hiding them, retries transient failures once, and adds an
exclusion-rate guard.

anchor-semantic-judge — the judge scores absolutely with nothing to anchor the
scale, and its opinion is blended into the composite at weight 0.25 as if it
were a measurement. The fix anchors the judge to the reference solution, adds a
worked score ladder, removes semantic from the composite, and measures judge
agreement across two models.

## How to work in this repo

- Use OpenSpec. Run /opsx apply <change-name> and work the task list.
- Every task names how to verify it. Do the verification, don't assert it.
- Docs are tasks in the same group as the code, deliberately. The last two
  defects were both partly caused by documented behaviour not matching the code.
- Run .venv/bin/python -m pytest -q before claiming anything is done. Baseline is
  208 passed, 2 skipped.
- Run .venv/bin/python -m codegen_evals.cli validate to check corpus soundness.
  Baseline is 20 specs, 40 suite runs, all sound.

## Known environment facts, do not rediscover these

- Node and openspec are at /opt/homebrew/bin — it is NOT on the default PATH.
  Prefix with: export PATH="/opt/homebrew/bin:$PATH"
- The opencode CLI is at /opt/homebrew/bin/opencode and ~/.opencode/bin/opencode
- The claude CLI is at ~/.local/bin/claude (a native install). `which claude`
  fails because ~/.local/bin is not on PATH. This is expected, not a fault.
- python3 is the system 3.9; the project venv is at .venv/
- If git add is blocked by permissions, retry with /usr/bin/git

## Two things I care about more than speed

1. If a result looks like a finding, check for an alternative explanation before
   reporting it. Every real bug in this project so far has been a failure that
   looked like a result.
2. If a change makes earlier numbers incomparable, say so plainly rather than
   quietly re-running. Both of these changes do exactly that.

## Current state

4 commits. Everything committed, working tree clean.
reports/*.json are from before both changes and will be stale once they land.
The explainer artifact at .lavish/explained-like-im-five.html is current as of
the last session.
