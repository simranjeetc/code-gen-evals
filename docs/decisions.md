# Decision log and lessons

A running record of the decisions this project has made and what it learned from
them. The goal: someone who reads **only this file** should understand what was
decided, why, and what went wrong along the way — without reconstructing it from
git history or the archived change designs.

## How to maintain this

- Every change with a `design.md` has decisions labelled `D1`, `D2`, … Add a row
  for each here when the change is archived, not before.
- When a measurement changes what is true, update the **measurement log**, not
  the prose of an old decision. Decisions are dated; they are not rewritten.
- When a defect repeats, add it to **lessons** with a reference to each instance.
  A lesson that has only happened once is an anecdote; two or more is a pattern.
- Record **rejected alternatives** in the decision row, not just the choice. The
  rejected option is the part that is hardest to recover later.
- Never quietly change a threshold. If a number moves, it moves as a new dated
  decision with the evidence that moved it.

## Decision log

### Change: `separate-harness-failures` — 2026-10-03 (schema 1 → 2)

| ID | Decision | Why | Rejected alternative |
| --- | --- | --- | --- |
| D1 | Classify outcomes at the **provider boundary**, not in the scorer | The provider is the only place that knows *why* a call failed; a scorer can only see a missing value | Classify in the scorer — loses the reason |
| D2 | A **sandbox crash is `scored`**; a **harness crash is `provider_error`** | The harness working while the model's code fails is a real measurement; the harness failing is not | Treat both as failures — conflates two different facts |
| D3 | **Exclude** infrastructure failures from aggregates, but **never hide** them | A failure must not deflate an average; it also must not disappear | Drop them silently — hides the harness's own reliability |
| D4 | **One retry** with a longer budget, only for **transient** outcomes | A transient failure is not a model property; `unparseable_output` is not transient and is not retried | Retry everything — inflates the sample and masks real failures |
| D5 | The **exclusion-rate guard** is separate from the **degenerate guard** | "Too many attempts were not measurements" and "the corpus measured nothing" call for different fixes | One combined guard — loses which problem you have |
| D6 | **Bump the schema version** | Attempts gained an `outcome`; older files are stale, not merely old | Keep one version — older files would look comparable when they are not |
| D7 | **Documentation is a task**, not an afterthought | The last two defects were partly documented behaviour that disagreed with the code | Docs after the fact — the disagreement ships |

### Change: `anchor-semantic-judge` — 2026-10-04 (schema 2 → 3)

| ID | Decision | Why | Rejected alternative |
| --- | --- | --- | --- |
| D1 | **Anchor the judge to the reference solution**; do not ask for an absolute score | With nothing to anchor it, the judge invents a scale on every call | Absolute rubric — not reproducible |
| D2 | Add a **worked score ladder** (1.0 / 0.5 / 0.0) as well as the anchor | Bands must be defined, not inferred | Anchor alone — bands still drift |
| D3 | **Remove `semantic` from the composite** | An opinion blended into a measurement is the defect the design exists to avoid | Keep semantic at weight 0.25 — the original defect |
| D4 | **Rebalance objective weights to sum to 1.0** | After removing semantic, the remaining weights must not silently renormalise | Leave weights — the composite changes meaning silently |
| D5 | **Measure agreement across two judge models**, over the references | Judge reliability must be disclosed, not assumed | Assume the judge is stable — unfalsifiable |
| D6 | **Human spot-check is a separate, later step** | No point validating a judge known to be badly designed; anchor first | Validate now — wastes the effort |
| D7 | **Mark `semantic` as derived in the data**, not only in prose | A consumer reading the JSON must see it is an opinion | Document it only — the data still lies by omission |

### Change: `add-pass-at-k-variance` — 2026-10-06 (schema 3 → 4)

| ID | Decision | Why | Rejected alternative |
| --- | --- | --- | --- |
| D1 | Report **spread**, name it **repeat stability** — **not `pass@k`** | `pass@k` means "passed at least once in k tries" (luck); we want the opposite (wobble) | Call it `pass@k` — a category error |
| D2 | A repeat is **k independent attempts**; a **retry is not one of them** | A flaky provider must not be able to inflate the sample | Count retries as repeats — inflates *n* |
| D3 | Statistics over **scored attempts only**; a pair with <2 scored repeats reports **`not_measured`, never `0.00`** | A zero would look like *evidence* of stability; it is absence of evidence | Report `0.00` — the same defect as a failure scored zero |
| D4 | **Variance guard** on within-model sd; threshold **0.05**, rule **2×sd** | A model whose own score moves cannot be ranked against another | No guard — gaps read as real |
| D5 | Add a **deliberately weak control model** | Measures whether the corpus can discriminate at all, instead of assuming it | Add more peer models — reproduces the tie |
| D6 | Logging: **one line per model by default**, `-v` for per-attempt, **one line per guard** | "Not too verbose, but I can tell what happened" | Structured JSON logs — a human is reading a terminal |
| D7 | **Bump the schema version** | Attempts gained a `repeat` index and runs gained variance; older files are stale | Keep version — variance-free files look comparable |
| D8 | **Documentation lands with the code** | Same reason as the previous two changes | Defer docs |

Session decisions outside a change (2026-10-06):

| Decision | Why | Rejected alternative |
| --- | --- | --- |
| Control model = **`opencode-go/qwen3.8-flash`** | Interpretable: a named Qwen *flash* (small) tier from a family absent from the bank | `space-bunny-free` (free but uninterpretable, unproven tool-calling); `muse-spark-1.3-contributor` (cheapest but "contributor" conveys no tier); `mimo-v2.5` / `deepseek-v4-flash` (same families as subjects) |
| Calibration at **k=3** for the first measurement | Minimum for a standard deviation; k=5 only if borderline near 0.031 | k=5 first — 1.7× the wall-clock before knowing if it was needed |
| **Postpone the LinkedIn post** until the corpus can rank models | The corpus currently does not discriminate; a leaderboard would be fiction | Post the current ranking — it is noise |

### Change: `add-harder-specs` — planned (no schema bump; corpus 20 → 30)

| ID | Decision | Why | Rejected alternative |
| --- | --- | --- | --- |
| D1 | The **hidden suites are the instrument**, not the prompt | 58/60 attempts pass every ground-truth test; longer prompts change nothing | Harden the prompts — effort without discrimination |
| D2 | **Difficulty recipe**: four axes; explicitly *not* longer prompts or more boilerplate | Targets what actually fails a model | "Make them longer" — raises effort, not discrimination |
| D3 | A spec is **accepted only if it discriminates** (fails at least one model) | The current 10 "hard" specs are labelled hard and scored 0.93 by everyone | Trust the authoring label — the label was never tested |
| D4 | **Acceptance rule fixed before** the calibration run (control separated, or spread > 0.10 with sd ≤ 0.031) | Deciding "hard enough" after seeing numbers is how a benchmark lies to itself | Set the threshold after — post-hoc rationalisation |
| D5 | **Ten original specs**, each a novel problem | Addresses difficulty and training-data contamination together | Harder versions of famous problems — reproduces contamination |
| D6 | Corpus grows; the report **states the size and flags non-comparability** | A 30-spec average is not comparable to a 20-spec average | Silently grow — mixes incomparable aggregates |
| D7 | **Documentation lands with the code** | Same reason as the previous three changes | Defer docs |

## Measurement log

Every run, what it showed, and whether it is comparable. A run is only
comparable with another of the **same schema version and corpus size**.

| run | date | schema | specs | k | models | what it showed | comparable? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `results-live20-v3.json` | 2026-10-04 | 3 | 20 | 1 | 4 | Spread 0.063; "hard" scored above "medium" | Historical (schema 3, k=1) |
| `results-live20-v4.json` | 2026-10-06 | 4 | 20 | 3 | 4 + control | Spread **0.023**; top two within 0.002; **control not separated**; 0 excluded; tiers monotonic | Current baseline |

The v3 → v4 comparison is the project's central finding: **a single-sample
"spread" of 0.063 collapsed to 0.023 under repetition, and the difficulty
ordering that looked wrong at k=1 became correct at k=3.** The 0.063 was noise.

## Lessons

### L1 — A failure rendered as a confident number (three instances)

The recurring defect. A thing that is *not a measurement* is rendered as one:

1. A provider timeout scored `0.0`, indistinguishable from bad code → produced a
   **false finding** (spread 0.11 collapsed to 0.035 when removed by hand).
2. A judge with nothing to anchor it produced a confident absolute score that was
   blended into the composite as if measured.
3. A single sample reported as a ranking, when the "ranking" was run-to-run noise.

**Rule:** whenever a number can be produced without the thing it claims to
measure, that is the bug. Ask "what is this number made of" before believing it.

### L2 — A single sample is not a finding; measure variance first

The 0.063 spread was one draw. At k=3 the same corpus gave 0.023, and the tier
ordering corrected itself. **No gap was ever reportable without a noise floor.**

### L3 — Test the instrument with a control before trusting its output

A deliberately weak model cost almost nothing and answered the question the
leaderboard could not: *can this corpus discriminate at all?* It could not. A
benchmark that has never been shown to separate a known-weak input is not
evidence of anything.

### L4 — Fix the accounting before changing what is accounted for

Changes were ordered deliberately: classify failures (schema 2) → anchor the
judge (schema 3) → measure variance (schema 4). Changing the judge while timeouts
still scored zero would have produced a different-shaped wrong answer.

### L5 — Decide acceptance thresholds before seeing the numbers

Every change fixed its rule in `design.md` while the result was still abstract:
the 2×sd rule, the 0.05 variance threshold, the 0.10 spread acceptance. The
temptation to move a goalpost after a disappointing result is the thing this
prevents.

### L6 — If a result looks like a finding, check the alternative explanation

Every real bug in this project was a failure that *looked like a result*. Before
reporting a finding: is there a simpler explanation (harness failure, single
sample, judge drift, selection)?

### L7 — When numbers become incomparable, say so plainly

Schema bumps and corpus growth each break comparability. Each change states it
in the proposal, marks old files historical, and never silently re-runs to hide
the break. Silence here would itself be the defect.

### L8 — Difficulty is a claim that must be tested, not a label

Ten specs labelled "hard" scored 0.93 for every model. The label was never
checked. A tier is a measurement or it is marketing.

### L9 — Documented behaviour that disagrees with the code is a defect

Two of the early bugs were partly a doc describing behaviour the code did not
have. Docs are tasks in the same group as the code, deliberately.

### L10 — Absence of evidence is not evidence of absence

A spread of `0.00` from one repeat, and a missing control model, both *look like*
good news. Both are the absence of a measurement. Render them as `not_measured`,
never as a passing value.

### L11 — Cost is usually not the constraint; wall-clock is

The k=3 run cost well under $1 and took 2h24m. The decision that mattered was
wall-clock, not money. Budget attention accordingly.

## Open questions

- **Does the style dimension belong in the composite?** Models score 0.65–0.76
  against a 0.598 reference, and style is the only dimension with headroom. It
  caps the composite near 0.95. This is a *scoring* question, deferred to its own
  change.
- **Can the control model be separated at all?** `qwen3.8-flash` scored mid-pack.
  If genuinely hard specs still cannot separate it, the model-bank question
  reopens (roadmap 10).
- **Contamination.** The existing 20 specs are famous problems. The new specs are
  original, but the old ones remain uncontrolled (roadmap 5).
- **Human validation of the judge.** Still the only measurement that checks judge
  *correctness* rather than stability. Deferred since `anchor-semantic-judge` D6.
