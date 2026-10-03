**Two things: what "broader bank" means, and an honest answer on publishing.**

## What I meant by "broader bank"

"Bank" is just **the list of models you test**. Right now it's four names in `config.py`:

```
opencode-go/deepseek-v4-pro
opencode-go/deepseek-v4.1-flash
opencode-go/mimo-v2.6-flash
opencode-go/longcat-2.5-preview-free
```

"Broader" means **more models, and more different kinds of models** — the opposite of my current situation, where all four are from the same family, same provider, similar quality. Four DeepSeek cousins tying is not surprising.

A broader bank would mix:

- different labs (Anthropic, OpenAI, Meta, Google, Mistral)
- different sizes (tiny on-device vs frontier)
- different ages (a 2023 model vs a 2026 one) — this alone would separate

**Why it matters here:** if four similar models tie, there are two explanations — (a) the puzzles are too easy, or (b) the models are too alike. You can't tell them apart. A broader bank tells you which: if a weak old model scores badly on the *same* puzzles, the puzzles are fine and the bank was too narrow.

That's exactly why I said "if the 5 hard specs still don't separate, the answer is a broader bank." It's the control experiment.

## Can this be published as a utility others can use? Honestly: not yet.

**What already works.** Anyone can clone it, run `make quickstart` in ~40s with no credentials, and get a report. `--models` takes any model name. The provider layer is pluggable and documented. That's a real foundation.

**The gap.** That's a *repo*, not a *utility*. Publishing means someone can grade their own model without understanding your code. Today they can't. Concretely, what's missing:

| Gap | Why it blocks a stranger | Work |
| --- | --- | --- |
| **Only one real backend is easy** | `opencode` needs your OpenCode install. Anthropic/OpenAI/Together work but need keys and weren't the tested path | small |
| **No install path** | not on PyPI; you clone and `pip install -e .` | small |
| **No "point it at my model"** | the likely ask is "I have an endpoint, grade it" — needs a generic OpenAI-compatible provider | small |
| **Corpus is not defensible** | 15 famous puzzles, no contamination control, and no evidence it discriminates | **large** |
| **Single-run numbers** | no pass@k, so no variance or confidence | small |
| **Judge bias unmeasured** | a stranger will ask "how do I know your judge is fair?" | medium |
| **No versioning or leaderboard stability** | scores change when you edit the corpus; nothing pins them | medium |
| **No sandboxing** | you execute untrusted code; a stranger running someone else's model has no cage | large |

**The honest read:** the *engineering* to publish is maybe a week. The *credibility* is the real work — and you're already on it. The corpus is the weak point. A benchmark nobody trusts is worse than no benchmark, because people quote the numbers.

**A realistic path, in order:**

1. **Prove it discriminates** — land the 5 hard specs, add pass@k, show a real spread with a broad bank. Without this there's nothing worth publishing.
2. **Add an OpenAI-compatible provider** — one class, and suddenly anyone with any endpoint can use it. Highest leverage single change.
3. **Sandbox execution** — a container per run. Without this you cannot responsibly tell strangers to run model-authored code.
4. **Publish to PyPI + a one-command entry point** — `codegen-evals run --provider openai-compatible --base-url ... --models my-model`.
5. **Then** write it up: methodology, limitations, a reproduction command.

**What I'd refuse to publish today**, and why: the current report shows `0.95` vs `0.98` on four near-identical models with a corpus that can't discriminate. Published like that, it invites someone to rank models on noise. That's the failure mode worth avoiding — a benchmark that looks authoritative and measures nothing.

**The useful reframe:** this isn't a product yet, it's a *measurement instrument you built for yourself*. Instruments get published after they've been shown to produce a repeatable reading — not before.

So: yes to your three (hard specs, pass@k, contamination). Then step 2 above — the OpenAI-compatible provider — is the single change that turns this from "your repo" into "something a stranger can point at their model."
