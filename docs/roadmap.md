# Roadmap

Ideas with evidence behind them, ordered roughly by value. Nothing here is
committed to; each entry records *why* it's worth doing and what it would take,
so the reasoning survives even if the idea is later dropped.

Status key: `idea` · `planned` · `in progress` · `done` · `rejected`

---

## The framing these all share

The framework's real nature is not "a Python grader". It is:

> Give it a fixed task and a variable input; it grades the resulting artifact on
> four axes and reports where they disagree.

Python functions are just the first artifact it was pointed at. The variable
could be a model, a prompt, an AGENTS.md file, a temperature, or a retrieval
strategy. **The architecture generalises; the corpus does not.** Every new target
needs new specs written for it, and writing those specs is the actual work.

---

## 1. Prompt and instruction evaluation

**Status:** `idea`
**Value:** high — every team writes an AGENTS.md and nobody knows if theirs works
**Effort:** small

### The insight that makes it cheap

A prompt is not the artifact being graded. **The prompt is the experimental
condition.** Today:

```
fixed prompt + varying model   →  grade the code
```

For prompt work:

```
fixed task + varying prompt    →  grade the code
```

All four dimensions survive untouched. We are still grading generated code with
`execution` / `edge` / `semantic` / `style`. What changes is the axis being
swept, not the scoring. Implementation is roughly a `prompt_variant` field on the
spec plus relabelling the report's "model" column.

### Questions this would answer with evidence

- Does a longer AGENTS.md help, or just cost tokens?
- Do instructions like "always add type hints" or "prefer the standard library"
  actually change the output?
- Does a prompt tuned for one model degrade another?
- Does adding examples help more than adding rules?

### What does NOT generalise

Scoring a prompt's *quality* directly — "helpful, unambiguous, well-scoped" — is
a different problem and should be resisted. pytest cannot assert it. It would need
a judge rubric plus a human-agreement study before any number meant anything.
That is a new eval method, not a new corpus, and it is the kind of thing that
looks scientific without being so.

### Not yet

Do this **after** the corpus can discriminate models. Shipping a prompt sweep on
top of a corpus that ties four models just moves the tie to a new axis.

---

## 2. Grading a repository's conventions

**Status:** `idea`
**Value:** medium
**Effort:** medium

Closely related to (1) but harder: an AGENTS.md is a single file, whereas "this
repo's conventions" is a *context* assembled from several files. Needs a way to
express "this bundle of text is the condition", rather than a single prompt
string. Probably falls out of (1) if the variant field accepts a file path.

---

## 3. Agent behaviour evaluation

**Status:** `idea`
**Value:** high, different market
**Effort:** large — needs a different harness

An agent's output is not code, it is a **trajectory**: which tools were called, in
what order, whether it recovered from failure, whether it asked for help, how many
steps it took. "Did it write correct code" is not the question; "did it behave
sensibly" is.

Some dimensions carry over — `execution` becomes "did the task complete" — but
`style` and `semantic` do not map cleanly onto a trajectory. This needs new
dimensions, not new specs.

### Likely to live in a separate utility

The shared parts are the corpus loader, the provider layer, scoring aggregation,
and reporting. The different parts are everything that makes the current tool
specific to code. A sibling utility that imports this one's internals is probably
cleaner than widening this one.

---

## 4. Pass@k

**Status:** `planned`
**Value:** high
**Effort:** small

Run each spec k times and report variance. Distinguishes a model that is reliable
from one that got lucky on a single sample. Nearly free: the provider loop and
`--concurrency` already support repeats; the schema needs a repeat index and the
report needs a variance column.

---

## 5. Contamination check

**Status:** `planned`
**Value:** high
**Effort:** small

The current 15 specs are famous problems. Reword prompts and compare against the
verbatim versions. A large drop on the reworded prompt is evidence the model
recognised the task rather than solved it. This is the most awkward unanswered
question about the existing corpus.

---

## 6. Instruction-following constraint

**Status:** `idea`
**Value:** medium
**Effort:** small

Add a constraint to a spec's prompt ("no loops", "standard library only",
"recursion forbidden") and check it is honoured. Genuinely discriminating, and
cheap because the constraint can be checked mechanically rather than by a judge.

---

## 7. OpenAI-compatible provider

**Status:** `planned`
**Value:** high for adoption
**Effort:** small

One class. Suddenly anyone with any endpoint can grade their own model:
`--provider openai-compatible --base-url ... --models my-model`. This is the
single change that turns the repo into something a stranger can point at their
own model.

---

## 8. Candidate subject types (new corpora)

**Status:** `idea`
**Value:** varies
**Effort:** medium to large per type

New artifacts the same four dimensions could grade, each needing its own specs:

| Candidate | Fits the four dimensions? | Notes |
| --- | --- | --- |
| SQL query generation | ✅ well | executable against a seeded DB; `edge` = unusual schemas |
| Regex / parser authoring | ✅ well | testable against sample corpora; `edge` = adversarial strings |
| Infrastructure as code | ⚠️ partly | `terraform validate`/`plan` as execution; edge is harder to bound |
| Shell scripts | ✅ mostly | but the sandboxing gap becomes serious |
| Test writing itself | ⚠️ inverted | the artifact is a suite; "execution" means does it catch seeded bugs |
| Commit messages / docs | ❌ no | nothing to execute; needs judge-only scoring |

---

## 9. Sandboxing execution

**Status:** `idea`
**Value:** required for publishing
**Effort:** large

Model-authored code currently runs on the host with a temp directory and a
timeout. That is fine for your own machine and **not** fine to recommend to
strangers. A container per run is the honest minimum before telling anyone else
to run this against a model they do not control.

---

## 10. Model and prompt bank breadth

**Status:** `idea`
**Value:** high
**Effort:** small

The current bank is four names from the same family. Four cousins tying is not
evidence the corpus is bad; a broader bank is the **control experiment** that
tells you which it is. Drop in one weak, old model against the same specs: if it
scores badly, the corpus is fine and the bank was too narrow.

---

## 11. Subscription-CLI providers (Claude Code, Codex CLI, OpenCode)

**Status:** `idea` — partially already done
**Value:** high — unlocks models that have no API path
**Effort:** small, but with a real catch

Several subscriptions expose a **CLI**, not an API. You have a prompt and an
agent that answers, and that is the only way to reach that model:

| Subscription | CLI | Reachable here? |
| --- | --- | --- |
| OpenCode Go | `opencode run` | ✅ already the default provider |
| Claude Code | `claude -p` | not installed on this machine |
| Codex CLI | `codex exec` | not installed on this machine |

### The good news

The provider layer is already built for exactly this. `OpenCodeProvider` shells
out, parses NDJSON, and extracts a fenced block. A `claude -p --output-format
json` provider is the **same shape** — a subprocess, a parser, an extractor. It is
maybe 40 lines, and the scoring layer never learns the difference.

### The catch, and it is not a small one

**"Just give it a prompt" is not true for a coding agent CLI.** These tools are
agents. Installed in a repo, `claude -p "write me a function"` may read files,
run shell commands, or edit the working tree. That is not a completion; it is an
agent run. Two consequences:

1. **It is not a clean measurement.** The model's answer now depends on the
   repository it happens to be sitting in. Two runs on two machines are not
   comparable.
2. **It can change your files.** A subject that edits the repo is not a subject;
   it is a collaborator.

This is exactly the reason the OpenCode provider pins
`.opencode/agents/codegen-eval.md` with every tool denied. A Claude Code provider
must do the same thing — run from a **scratch directory** outside the repo, with
tools denied via `--allowedTools ''` / `--disallowedTools`, and ideally a
`--strict-mcp-config` to make sure no MCP server leaks capability in.

### Where it is genuinely fine

Grading **prompt and instruction artifacts** (roadmap 1) is a much better fit for
a CLI agent than bare code generation is, because that is what agent CLIs are for
— reading an AGENTS.md, interpreting it, and acting. If the roadmap goes that
way, a Claude Code provider becomes the *right* tool rather than a compromise.

### Verifying before building

A provider must be proven to produce a clean code block with **no tool calls and
no file writes** before its numbers are trusted. Verification is the same shape as
the OpenCode check: run it in a scratch dir, assert no tool events and no new
files, compare the output to a bare completion.

### Installation on this machine (verified 2026-10-03)

Claude Code **is** installed and does not need installing:

```
/Users/simran/.local/bin/claude  ->  ~/.local/share/claude/versions/2.1.286
```

It is a *native* install (`installMethod: native` in `~/.claude.json`), which is
why no npm global exists and why `which claude` fails: **`~/.local/bin` is not on
PATH**. The provider must locate it explicitly rather than relying on `which`,
the same fallback pattern already used by `find_opencode()`.

### Verified invocation shape

`-p/--print` is genuinely headless and does not need a TTY, so shelling out works.
`--output-format json` returns a **single JSON object**, not NDJSON like OpenCode:

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "result": "```python\ndef add(a, b):\n    return a + b\n```",
  "num_turns": 1,
  "duration_ms": 191,
  "total_cost_usd": 0,
  "permission_denials": [],
  "modelUsage": {},
  "session_id": "..."
}
```

The answer is `result`, so the parser is a one-liner compared to OpenCode's NDJSON
walk. Two extra fields are worth surfacing in the report:
`permission_denials` (proof no tool was attempted) and `num_turns` (should be 1
for a bare completion — more means the agent acted).

### The blocker

A live call currently fails:

```
"result": "Failed to authenticate: OAuth session expired and could not be refreshed",
"is_error": true, "terminal_reason": "api_error"
```

The OAuth session has expired, so the provider **cannot be verified** until
`claude` is re-authenticated interactively. Building it blind would repeat the
exact mistake this project already made once (the judge path that silently
abstained for 40/40 results). A provider is not done until a live call returns
extractable code.

### Verified: no files written

The scratch-directory run created nothing:

```
$ ls -la "$SCRATCH"    # empty
```

With `--disallowedTools` covering the file and shell tools, the reported
`permission_denials` was `[]` and the working directory stayed clean. That is the
containment the roadmap requires before any CLI-agent provider's numbers are
trusted.

### What the provider needs

Run from a scratch directory outside the repo, with all tools denied and MCP
disabled to stop capability leaking back in:

```
claude -p "<prompt>" \
  --output-format json \
  --model <alias> \
  --disallowedTools Bash Edit Write Read Glob Grep WebFetch WebSearch Task \
  --strict-mcp-config
```

Then assert, before trusting any number: `is_error` is false, `num_turns == 1`,
`permission_denials` is empty, and a fenced block came back.

---

## 12. Publishing and credibility

**Status:** `idea`
**Value:** the actual deliverable
**Effort:** the credibility row is the real work

What stands between this and something a stranger can use is **not** mostly code.
Engineering to publish is roughly a week; the gating items are:

| Gap | Work |
| --- | --- |
| Point it at *my* model | small — roadmap 7 |
| Install path (PyPI) | small |
| Only one easy backend | small — roadmap 11 |
| Variance (pass@k) | small — roadmap 4 |
| Judge fairness evidence | medium |
| Versioning / stable scores | medium |
| **Corpus credibility** | **large — the real work** |
| **Sandboxing** | **large — roadmap 9** |

### What should not be published yet

The current report shows 0.95 vs 0.98 across four near-identical models on a
corpus that cannot discriminate. Published as-is, it invites ranking models on
noise. A benchmark that looks authoritative and measures nothing is worse than no
benchmark, because people quote the numbers.

### Positioning

Not "a Python grader". Not "eval tooling". The offer is **the ability to answer a
question with evidence: which model, for which task, and where it breaks.**
Potential directions, best fit first: model-eval consulting, custom domain evals,
a hosted leaderboard (later — sandboxing becomes your liability), selling the
tool (weakest — the space is crowded and largely free).

---

## In flight — start here next session

Two OpenSpec changes are ready to implement and are the immediate next work. Both have `proposal.md`, `design.md`, `specs/`, and `tasks.md` at 4/4 artifacts, validated strict.

### `anchor-semantic-judge` — the judge is not trustworthy yet

The semantic dimension asks a judge for an **absolute** score with nothing to anchor it, so the judge invents a scale on every call. Worse, it is blended into the composite at 0.25 as if it were a measurement, alongside three dimensions that genuinely are objective.

- **Fix:** give the judge the reference solution and ask it to *compare* rather than rate; add worked 1.0/0.5/0.0 examples; **remove semantic from the composite** and show it as a separate opinion column; measure judge agreement across two judge models; mark it as judge-derived in the data.
- **Cost:** all existing results become incomparable. Stated in the proposal, not hidden.
- **Deferred deliberately:** human validation. There is no point asking a human to validate a judge that is known to be badly designed. Anchor it first (task 6), then validate.

### `separate-harness-failures` — a failure is currently rendered as a score

A provider timeout or crash is scored `0.0`, indistinguishable from a model that wrote bad code. This produced a **false finding**: a four-model run appeared to break the tie with a spread of `0.11`, which collapsed to `0.035` once three infrastructure failures were removed by hand.

- **Fix:** classify every attempt (`scored` / `timeout` / `provider_error` / `unparseable_output`), exclude infrastructure failures from aggregates while still reporting them, retry transient failures once with a longer budget, raise the default timeout, and add an exclusion-rate guard.
- **Key distinction:** a sandbox crash is `scored` (the harness worked, the model's code did not); a provider failure is not.

Both are the same defect class as the judge bug that abstained for 40 of 40 results: **a failure rendered as a confident number.** A sweep for other instances is covered by task 5 of the second change.

---

## Rejected

### Scoring prompt quality directly

**Status:** `rejected`

Covered under (1). pytest cannot assert "this prompt is good", and an LLM judge
without a human-agreement study produces a number that looks authoritative and
means nothing. Rejecting this is a decision worth keeping visible, because it
will be proposed again.

### Selling the tool as software

**Status:** `rejected`

Eval tooling is crowded and largely free. The sellable thing is the *ability to
answer a question* — which model, for which task, and where it breaks — not the
runner. See the publishing section of the explainer artifact.
