**Four questions. Two of them have a blunt answer, so let me give that first.**

## What does the mock actually do for us?

You're right to push on this. In a CI run it proves one thing only: **the machinery works** — corpus loads, prompts render, code executes, JUnit parses, scores compute, the report renders. If someone clones the repo, the mock tells them the harness isn't broken before they spend money on real models.

But it gives **zero signal about model quality**, and I should be honest that this is a weak justification. A test suite would cover most of that. The mock's real value is narrower than the artifact implies: it lets a contributor change scoring code and see the effect on a report *without paying per run*. That's it. It is not a smoke test anyone actually needs in production, and I would not defend it as one.

**So: keep it as a development convenience, not as a feature.** The artifact oversells it.

## Is this utility just "rate a model's code ability"?

Mostly yes — but the sharper framing is: **it measures where a model's competence stops.**

A single "can it code?" score is what every other benchmark already gives you. What this gives you is *where it breaks*: passes the tests but misses the point, works on the obvious case and dies on the edge, correct but unreadable. The rating is the byproduct; the failure map is the product.

## What test flavors can it do tomorrow?

Real options, ordered by usefulness:

| Flavor | What changes | Effort |
| --- | --- | --- |
| **Harder specs** | corpus content | already planned — 5 new hard ones |
| **Different languages** | add C++ / Go / Rust corpora | prompt + entrypoint convention per language; the framework is language-agnostic already |
| **Repo-level tasks** | multi-file, not single-function | needs a new spec type: "here's a codebase, fix this bug" |
| **Contamination check** | same spec, reworded vs verbatim | cheap, and it directly answers "did it memorise FizzBuzz?" |
| **Pass@k** | run each spec k times, check variance | one config change; tells you if a model is reliable or lucky |
| **Prompt sensitivity** | same spec, 5 phrasings | cheap; reveals models that only work when asked a specific way |
| **Instruction following** | add constraints ("no loops", "stdlib only") | small spec change, genuinely discriminating |

The last two are the cheapest wins and probably the most revealing. Pass@k is genuinely one-line-ish: your `--concurrency` and provider loop already support repeats.

## Can we try a different model tomorrow?

**Yes, and it's the easiest thing in the whole repo — no code changes.** Models are just strings:

```
--models "opencode-go/anything-you-have"
```

Add one to the bank in `config.py`, or pass `--models` on the command line. The two constraints are real though: the judge must be a *different* model (enforced in code), and a model needs to be reachable by a provider — either your OpenCode subscription or a public API key.

## Can we create a different model tomorrow?

No — and this is worth being blunt about. Creating a model is **training**, which needs data, GPUs, and weeks. Nothing here does that. This framework *measures* models; it does not make them.

If what you mean is **"can we build our own thing on top of an existing model"** — a fine-tuned variant, a prompt wrapper, an agent — then yes: fine-tune something, point it at any OpenAI-compatible endpoint, and add a provider adapter. That's maybe 30 lines (see `docs/providers.md`). But that's building a *product* on a model, not building a model.

## What I'd do next, in order

1. **Land the 5 hard specs** (already planned) and see if the bank separates at all.
2. **Add pass@k** — cheapest, and it tests reliability rather than one lucky sample.
3. **Add the contamination check** — these are famous problems, so this answers the most awkward question about the current 15.

All three are small. If the 5 hard specs still don't separate the bank, the honest read is that this bank isn't separable at this corpus size, and the answer is a broader bank — not more infrastructure.
