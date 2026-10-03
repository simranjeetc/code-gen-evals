# Providers

A provider turns a prompt plus a model id into a `Generation`. Everything a
provider does is measured against the same contract, so scoring never needs to
know which backend produced the code.

## The contract

```python
generation = provider.generate(prompt, model_id, spec_id="fizzbuzz")
```

`Generation` carries:

| Field | Meaning |
| --- | --- |
| `raw_text` | exactly what the model returned |
| `code` | the extracted code block, or `None` |
| `extracted` | whether a usable code block was found |
| `error` | failure text, or `None` |
| `duration_s` | wall-clock seconds for the call |
| `params` | provider, model, temperature, and provider extras |

**Failures never raise out of `generate`.** A timeout, an HTTP 500, a missing
binary, or a response with no code block all come back as a `Generation` with
`error` set. One bad call cannot abort a run.

## Code extraction

Extraction happens once, in the provider layer, and is the only place that
decides whether the model produced code:

1. the first fence tagged `python`, `python3`, `python2`, `py`, or `py3`; else
2. the first **untagged** fence; else
3. extraction failure.

A fence tagged with another language (` ```javascript `) is *not* accepted, and a
response with no fence at all is an extraction failure. An unterminated fence
runs to the end of the text — models sometimes omit the closing fence and the
code is still usable.

An extraction failure scores execution and edge-case handling as `0.0` rather
than crashing the run.

## Choosing a provider

```bash
.venv/bin/python -m codegen_evals.cli run --provider mock
.venv/bin/python -m codegen_evals.cli run --provider opencode
.venv/bin/python -m codegen_evals.cli run --provider anthropic --models claude-sonnet-4-5
```

| Provider | Credential | Default models |
| --- | --- | --- |
| `mock` | none | `mock-strong`, `mock-mid`, `mock-weak` |
| `opencode` | none (uses local OpenCode auth) | the configured 4-model bank |
| `claude-code` | none (uses the Claude Code subscription) | `sonnet` |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-sonnet-4-5` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o` |
| `together` | `TOGETHER_API_KEY` | `meta-llama/Llama-2-70b-chat-hf` |

Selecting a public-API provider without its credential raises a
`ProviderConfigError` naming the exact environment variable. There is no silent
fallback to mock.

## The OpenCode provider

OpenCode models are driven through the local CLI:

```
opencode run --agent codegen-eval --model <model-id> --format json "<prompt>"
```

Output is NDJSON; every `text` part is concatenated and then extracted.

### Why an agent, and why tools are off

`opencode run` executes an **agent**, and the default agent has `bash`, `write`,
`edit`, and `read` enabled. That is wrong for this task: a run must measure
"given this prompt, what code comes out", not "an agent that can act on the
repository". A code-generation subject that writes files or runs shell commands
introduces side effects that are not code quality.

`.opencode/agents/codegen-eval.md` therefore denies every tool, sets
`temperature: 0`, and instructs the model to emit one fenced block:

```yaml
---
description: Bare Python code generation with no tools, for the eval harness.
mode: primary
temperature: 0
permission:
  read: deny
  edit: deny
  glob: deny
  grep: deny
  list: deny
  bash: deny
  task: deny
  webfetch: deny
  websearch: deny
  todowrite: deny
---
```

Because the agent blocks tool calls and pins temperature, differences in the
report are model differences rather than agent-behaviour differences.

### Verifying it works

```bash
opencode run --agent codegen-eval --model opencode-go/mimo-v2.6-flash \
  "Define add(a, b)." --format json
```

Expect a `{"type":"text", ...}` event containing a single fenced Python block
and no tool events. To run the same check as a test:

```bash
CODEGEN_EVALS_LIVE=1 .venv/bin/python -m pytest tests/test_providers.py -q -k live
```

That test is skipped by default so the normal suite stays offline.

## The Claude Code provider

Claude Code is a subscription product whose CLI is the only way to reach the
model — there is no API path for it. This provider shells out to `claude -p`,
which is genuinely headless and needs no TTY.

```bash
.venv/bin/python -m codegen_evals.cli run --provider claude-code --models sonnet
```

### Finding the binary

A **native** install lives outside `PATH`, which is why `which claude` can fail on
a perfectly working install. So the provider searches `PATH` first, then:

```
~/.local/bin/claude
~/.claude/local/claude
/opt/homebrew/bin/claude
/usr/local/bin/claude
```

Check with:

```bash
.venv/bin/python -c "from codegen_evals.providers.claude_code import find_claude; print(find_claude())"
```

### The catch: Claude Code is an agent, not a completion endpoint

Run in a repository, `claude -p "write me a function"` may read files, run shell
commands, or **edit the working tree**. That breaks the measurement in two ways:
the answer would depend on whatever repository it happened to be sitting in, and
the subject could change your files.

The provider therefore refuses to trust a run unless it was a **bare, tool-free,
single-turn completion**:

- runs from a **throwaway directory outside the repo**
- denies every tool (`Bash`, `Edit`, `Write`, `Read`, `Glob`, `Grep`, `WebFetch`,
  `WebSearch`, `Task`, `NotebookEdit`)
- passes `--strict-mcp-config` so no MCP server leaks capability back in
- rejects the result if `is_error` is set, if `permission_denials` is non-empty,
  if `num_turns` is greater than 1, **or if any file appeared in the scratch dir**

Those are hard failures, not warnings. A run that took four turns did not measure
code generation, so there is no honest score to compute from it.

### Output shape

Unlike OpenCode's NDJSON, this is a single JSON object:

```json
{
  "type": "result", "subtype": "success", "is_error": false,
  "result": "```python\ndef add(a, b):\n    return a + b\n```",
  "num_turns": 1, "duration_ms": 2301, "total_cost_usd": 0.06,
  "permission_denials": [], "modelUsage": {"claude-sonnet-5-5": {}}
}
```

`num_turns` and `permission_denials` are recorded with every result, so a report
can be audited for whether the subject was actually contained.

### Judging

The judge must be a **different** model, so pair a subject with a different alias:

```bash
--models sonnet --judge haiku
```

Passing the same alias for both is refused in code rather than silently producing
a self-graded semantic score.

## The mock provider

The mock provider is not a model. For each `(model_id, spec_id)` it hashes a
deterministic draw and picks one of four mutations of that spec's **reference
solution**:

| Variant | What it returns | Effect |
| --- | --- | --- |
| `perfect` | the reference, unmodified | full marks |
| `untyped` | reference with annotations and docstrings stripped | execution passes; style drops only if the reference had annotations or docstrings to begin with |
| `stub` | every required symbol replaced by a do-nothing stub | execution collapses |
| `empty` | an empty module | import fails |

The reference solutions are deliberately minimal — several have no annotations
or docstrings — so `untyped` is sometimes identical to `perfect`. The mock is
built to exercise the pipeline and the execution/edge dimensions; style-specific
disagreements are covered by unit tests on constructed fixtures rather than by
the mock run.

Skill per model comes from `MOCK_SKILLS` (`mock-strong` 0.85, `mock-mid` 0.60,
`mock-weak` 0.30) and controls how often `perfect` is drawn. Results are
byte-identical across runs.

**A mock run is pipeline validation, not a model comparison.** The variants are
synthetic by construction, and the report labels them as such.

## Adding a provider

1. Subclass `Provider` in `codegen_evals/providers/` and implement
   `_invoke(self, prompt, model_id, spec_id="") -> (raw_text, params)`.
2. Raise `ProviderConfigError` from `__init__` when the provider is not usable,
   naming what is missing.
3. Let `_invoke` raise freely on failure — `generate` captures it.
4. Register it in `codegen_evals/providers/__init__.py`: add the name to
   `PROVIDER_NAMES`, add a default model list to `_DEFAULT_MODELS`, and add a
   branch in `build_provider`.
5. Add a test that the provider is constructible and that a missing credential
   names the variable.

A provider only ever returns **text**. Extraction, scoring, and reporting are
shared, so a new backend cannot change how quality is measured.
