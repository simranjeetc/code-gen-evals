# Design

## Context

See `proposal.md` for the motivation. The relevant measured state, from the live run recorded in `reports/results-live.json`:

| Model | execution | edge | semantic | style |
| --- | --- | --- | --- | --- |
| `deepseek-v4-pro` | 1.00 | 1.00 | 1.00 | 0.76 |
| `deepseek-v4.1-flash` | 1.00 | 1.00 | 1.00 | 0.70 |
| `mimo-v2.6-flash` | 0.98 | 1.00 | 0.97 | 0.79 |
| `longcat-2.5-preview-free` | 1.00 | 0.97 | 0.94 | 0.66 |

Only two specs produced any failure at all: `rate_limiter` (`execution` 0.80 for `mimo`) and `csv_parse_line` (`edge` 0.75 for `longcat`). Both are already `hard` tier.

The diagnosis is specific: the existing hard specs mostly test *algorithmic* difficulty, and all four models are good at algorithms. What separates code-generation models is not whether they can write a topological sort — it is whether they notice the cases the prompt did not spell out.

## Goals / Non-Goals

**Goals:**

- Produce a corpus on which the default bank does not tie.
- Keep every existing spec and score untouched, so results remain comparable.
- Make the `edge` dimension a genuine separator by writing edge suites that test failure modes the ground-truth suite deliberately omits.

**Non-Goals:**

- Re-balancing or rewriting the 15 existing specs.
- Changing any scoring formula, weight, or threshold. If the corpus still fails to separate after this change, the next lever is the model bank, not more specs.
- Adversarial or adversarial-adjacent tasks (security exploits, deliberately hostile inputs). The goal is realistic production failure modes.
- Re-run cost control. A 4 × 20 run is 80 evaluations; that is accepted.

## Decisions

### D1: Grow to 20 as 5/5/10 rather than 6/6/8

Keep the easy and medium tiers at their current 5 and put all 5 new specs at `hard`.

- Why: the easy tiers are already saturated (1.00 across the board), so adding more there is pure cost with no signal. The `hard` tier is the only place any separation appeared.
- Alternative considered: add 2 easy, 2 medium, 1 hard (a proportional 6/6/8 split). Rejected: spends two fifths of the added budget on tiers we already know measure nothing.

### D2: Pick the 5 new specs from distinct failure-mode families, not distinct topics

Each new spec targets one *kind* of failure that the current corpus under-tests:

| Failure mode | Why models fail it | Draft spec id |
| --- | --- | --- |
| State machine over untrusted text | tokenising edge cases: unterminated input, escapes at end of string | `template_renderer` |
| Resource limits | ignores the cap, or enforces it off-by-one | `bounded_queue` |
| Numeric precision | naive float arithmetic accumulates error | `money_total` |
| Partial failure / ordering | assumes every step succeeds, or loses completed work | `batch_processor` |
| Multi-step protocol | handles the happy path only, not the mid-protocol abort | `state_machine` |

- Why: five specs on one axis (say, five more parsers) would add five correlated data points. Five different axes give the report five independent chances to separate models, and give the task-type section real buckets instead of single-spec ones.
- Alternative considered: five harder algorithm specs. Rejected: algorithms are exactly what all four models already do well, so this would reproduce the current tie at greater cost.

### D3: The edge suite must omit the happy path the ground-truth suite covers

New specs follow an explicit rule: the ground-truth suite covers behaviour stated or clearly implied by the prompt, and the edge suite covers behaviour the prompt does **not** spell out but that a careful implementation would handle. No test in one suite duplicates a test in the other.

- Why: the current corpus's weak point. If the edge suite largely repeats the ground-truth suite, `edge` tracks `execution` and both collapse onto "did the model write anything sensible", which is what happened.
- Alternative considered: give the edge suite the same tests plus extras. Rejected: duplicating tests makes the two dimensions correlated by construction.

### D4: Every new prompt states its contract without enumerating its edge cases

Prompts describe the required behaviour precisely but do not list the inputs the edge suite will try. Stating them would turn the edge dimension into a reading-comprehension test.

- Why: `edge` is only meaningful if the model has to reason about robustness rather than transcribe a list.
- Alternative considered: state the edge cases in the prompt for fairness. Rejected: it destroys the dimension's purpose, and a realistic production task rarely enumerates its own boundary cases either.

### D5: Keep the existing 15 byte-for-byte identical

No prompt rewording, no tag changes, no suite edits.

- Why: any edit to an existing spec invalidates comparison against `reports/results-live.json` and against any report already circulated. The prior results stay a valid baseline for the 15 shared specs.
- Alternative considered: also harden the existing specs' edge suites. Rejected for now: it would make the old and new runs incomparable in a way that is hard to explain, and mixing two changes makes it impossible to tell which one produced a difference.

## Risks / Trade-offs

- [The new specs may still not separate the bank, since these models are genuinely strong] → The tier and task-type breakdown, not only the composite, is the acceptance check. If 5 carefully-aimed hard specs produce no separation either, the honest conclusion is that this bank is not separable at this corpus size, and the next move is a wider model bank rather than more specs.
- [Hand-written edge suites are my judgement calls, and may encode what I happen to think is hard] → Each new edge suite must contain at least one test that fails a plausible-but-naive implementation. I will verify this by running a deliberately naive candidate against it, not only the reference.
- [More specs cost more time and tokens] → A 4 × 20 run is ~80 evaluations; the measured rate is roughly 14s per evaluation, so ~19 minutes. Acceptable, and the mock path stays free and offline.
- [Changing corpus size invalidates absolute comparisons with earlier reports] → Existing specs are unchanged, so per-spec comparison still holds. Only aggregates over "the whole corpus" shift, and metadata records the corpus size on every run.
- [Tier counts become uneven (5/5/10), which could skew a tier-weighted average] → Tier aggregates are reported per tier, never collapsed into one tier-weighted number, so an uneven count cannot distort a reported figure.

## Migration Plan

Additive only. New spec directories are added; nothing is removed or renamed. Rollback is deleting the 5 new directories and reverting the size assertions in `tests/test_corpus.py` and the counts in `docs/corpus.md`.

Existing reports under `reports/` are left in place. Re-running the full pipeline after the change produces new artifacts; the old ones are not overwritten.

## Open Questions

None blocking. Whether these five specific specs actually separate the bank is an empirical question answered by the acceptance run, not a design decision.
