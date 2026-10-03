**Saved to `docs/roadmap.md` — 12 entries, plus a Rejected section. And yes, Claude Code is supportable, but not the way you'd expect.**

## Where your points are saved

`docs/roadmap.md` in the repo, linked from the README. It's a backlog, not a spec — each entry records the *why* and the *effort*, including two entries I marked **rejected** with the reasoning kept visible, because both will be proposed again.

The framing that ties them together, and the one worth remembering:

> Give it a fixed task and a variable input; it grades the resulting artifact on four axes and reports where they disagree.

Python functions are just the first artifact. The variable could be a model, a prompt, an AGENTS.md, a temperature. **The architecture generalises; the corpus doesn't** — every new target needs new specs, and writing those specs is the actual work.

Your two questions are now entries 1 and 11.

## Your prompt/AGENTS.md idea, properly captured

The insight that makes it cheap: **a prompt isn't the artifact being graded — it's the experimental condition.**

```
today:    fixed prompt + varying model    →  grade the code
prompts:  fixed task   + varying prompt   →  grade the code
```

All four dimensions survive untouched. Only the axis you sweep changes. That's a `prompt_variant` field and a relabelled column — genuinely small.

I also recorded the part I'd **refuse**: scoring a prompt's *quality* directly. pytest can't assert "helpful, unambiguous", and an LLM judge without a human-agreement study produces a number that looks authoritative and means nothing.

## Claude Code: yes, and the catch is real

**The good news.** The provider layer is already built for exactly this. `OpenCodeProvider` shells out, parses NDJSON, extracts a fenced block. A `claude -p --output-format json` provider is the **same shape** — subprocess, parser, extractor, ~40 lines. Scoring never learns the difference.

**The catch.** "Just give it a prompt and it generates and ends" is not how a coding-agent CLI behaves. Installed in a repo, `claude -p "write me a function"` may read files, run shell commands, or **edit your working tree**. That's not a completion, it's an agent run. Two consequences:

1. **Not a clean measurement** — the answer depends on whatever repository it's sitting in. Two machines, two different results.
2. **It can change your files.** A subject that edits the repo isn't a subject.

This is *precisely* why the OpenCode provider pins `.opencode/agents/codegen-eval.md` with every tool denied. A Claude Code provider has to do the same: run from a **scratch directory outside the repo**, tools denied via `--disallowedTools`, and `--strict-mcp-config` so no MCP server leaks capability back in.

And it must be **proven** clean before its numbers are trusted — same check we ran on OpenCode: scratch dir, assert no tool events, assert no new files.

**Where it's genuinely the right tool:** grading **prompt and instruction artifacts** (entry 1). Reading an AGENTS.md and acting on it is what these CLIs are *for*. If the roadmap goes that way, a Claude Code provider stops being a compromise and becomes the correct choice.

## One correction

You mentioned "something similar is also supported by OpenCode as well" — **OpenCode isn't similar, it's already done.** It's the *default* provider. Every live number in this repo came from `opencode run`. So you have one working subscription-CLI provider today, and Claude Code would be the second.

Also worth knowing: **`claude` isn't on your PATH** on this machine. `~/.claude/` is fully populated (sessions, projects, plugins) and `/Applications/Claude.app` is installed, but no CLI binary resolves from your login shell. So the Claude Code provider can't be verified here until that's sorted — which is worth doing before we build it.

## What I'd do next, in order

1. **Commit** — still the blocker on everything (`git add -A && git commit`)
2. **5 hard specs** — planned and validated, ready to implement
3. **pass@k** — small, gives post 4 real numbers
4. **Claude Code provider** — *after* finding why the CLI is missing

Want me to start on 2, or look into the missing `claude` binary first?
