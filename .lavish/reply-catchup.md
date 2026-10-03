**You're right — replies 2 through 6 never reached the browser.** I was attaching `--agent-reply` to `poll` and piping through `tail`; the POST failed and I never noticed, because the failing command still streamed the poll banner. Only the very first reply landed. Fixed: I'm using `reply` now, which confirms delivery before exiting.

Here are the answers you were missing, in order.

## "0.5 for what?"

The judge gives **one number 0.0–1.0** for how well the code matches the *stated intent* — not a 5-point scale, not a percent of tests. 0.5 is the midpoint of three bands:

- **1.0** — fully and correctly implements what was asked
- **0.5** — partially correct, or correct only for the obvious case
- **0.0** — wrong, missing, or materially different from the request

It also writes a one-sentence rationale, stored with the result, so you can audit the call. Three bands from one LLM is a **coarse instrument** — a second opinion that catches "passed the tests but isn't what you asked for", not a precise measurement.

## Is there a baseline? A golden dataset?

**Two different things.** Yes, there's ground truth — each puzzle ships a reference solution plus hidden tests defining "correct", and `validate` confirms all 40 pass. Those are the "golden dataset" in the known-good sense.

**No, there's no model baseline.** Nothing says "here's what a strong model scores, here's the bar." Every number is relative to the others in the same run. Consequences: no absolute scale (is 0.94 good?), no floor (how badly does a bad answer score?), and no ceiling check — **if the reference solutions themselves don't score ~1.0, every model is penalised for something the answer key also fails.** I have never checked that, and I should.

## The tie is NOT broken — I nearly reported a false result

Three of eighty results in the 20-spec run were **infrastructure failures** (two timeouts, one provider crash), scored `0.00` and therefore indistinguishable from a model failing. Recomputing without them:

```
deepseek-v4.1-flash  0.969
longcat              0.962   (was 0.914)
mimo                 0.954   (was 0.859)
deepseek-v4-pro      0.935
```

Spread collapses from 0.11 back to **0.035**. Still a tie. The framework cannot currently tell "the model failed" from "our harness failed", which makes any published number unreliable.

## Two failure-as-score bugs now, not one

The judge that silently abstained, and the timeout scored as model weakness. Both are **a failure rendered as a score**. Worth a sweep for other places that happens rather than fixing them one at a time.

## What I'd do next, in order

1. **Run the reference solutions through the scorer** — the missing baseline. Minutes of work, and it either validates the scale or invalidates it.
2. **Fix infra-vs-model failure** — blocks publishing.
3. Add a **baseline row** to every report.

Start with 1?
