# Design

## Context

The measurement that licenses this change is `reports/results-live20-v4.json` (schema 4, 300/300 attempts scored, 0 excluded, 144 min). Its findings:

```
subjects                          composite   sd      maxspec_sd
deepseek-v4.1-flash               0.949       0.008   0.040
mimo-v2.6-flash                   0.948       0.016   0.041
longcat-2.5-preview-free          0.927       0.010   0.060
deepseek-v4-pro                   0.926       0.026   0.359
qwen3.8-flash  (control, weak)    0.927       0.025   0.232

subject spread 0.023; top two within 0.002; control NOT separated (gap 0.011)
per dimension (subjects): execution 0.981-0.997 | edge 0.969-0.999
                         semantic 0.957-0.972  | style 0.654-0.758
58 of 60 subject attempts pass every ground-truth test
```

Two facts drive the whole design:

1. **The control was not separated.** A deliberately weak small model scored mid-pack. That is the pre-registered meaning of "the corpus cannot discriminate; the model bank is not the limiting factor." (See `archive/2026-10-04-add-pass-at-k-variance/design.md`, D5.)
2. **Execution is trivially easy.** 58 of 60 attempts pass every hidden ground-truth test, and 54–59 of 60 pass the edge suite. The composite's movement is almost entirely `style`, and it is capped near 0.95 by the weights (`0.5·1 + 0.3·1 + 0.2·0.7 ≈ 0.94`).

So the defect is **not** prompt ambiguity. It is that the hidden suites do not fail competent models. Harder *prompts* would not fix it; harder *tests* will.

## Goals / Non-Goals

**Goals:**

- Add specs whose hidden suites genuinely fail competent models, so the corpus can rank them.
- Make the difficulty tier a *tested claim* rather than an authoring label.
- Fix the acceptance rule before seeing any result, so a weak batch cannot be rationalised into acceptance.
- Address training-data contamination at the same time, by authoring original problems.

**Non-Goals:**

- Rewording the existing 20 prompts. That is roadmap item 5 (contamination check) and would make the existing corpus incomparable with itself.
- Changing scoring, weights, providers, or the CLI. This is a corpus change plus the rule that judges it.
- Fixing the `style` ceiling. It is a real finding (models score 0.65–0.76 against a 0.598 reference) but it is a *scoring* question, not a corpus one, and belongs in its own change.
- Reaching a target model ranking. The goal is that the instrument *can* discriminate; whether it does is what the calibration measures.

## Decisions

### D1: The hidden suites are the instrument, not the prompt

A spec is hard when a competent model's code **fails its tests**, not when its prompt is long or its prose is dense. Every new spec is authored test-first against a plausible-but-wrong implementation: write the suite so that the naive solution passes the ground-truth cases and fails the edge cases, then write the reference that passes both.

- Why: the data says execution is 0.99 for everyone. Lengthening prompts changes nothing; failing the naive implementation changes everything.
- Consequence: the edge suite carries the discrimination. A spec whose edge suite a naive solution also passes is not hard and is rejected by D3.

### D2: The difficulty recipe — four axes, and what is explicitly not hard

Each new spec targets at least one axis, and its tags name it:

| axis | what makes it hard | example failure mode |
| --- | --- | --- |
| **precise multi-constraint compliance** | several interacting rules where satisfying one naively breaks another | a function that is correct except when two requirements conflict |
| **adversarial edge cases** | the edge suite targets the specific wrong-but-plausible implementation | naive solution passes ground truth, fails edges |
| **algorithmic subtlety** | easy to get ~90% right, hard to get fully right | an approach that handles the common case and silently mis-handles one |
| **exact specification of corners** | behaviour at boundaries is stated exactly and must be honoured, not inferred | off-by-one, tie-breaking, and empty-input rules |

**Explicitly not difficulty:** longer prompts, more boilerplate, more I/O plumbing, more named symbols. Those raise effort without raising discrimination, and the corpus already shows effort is not the bottleneck.

### D3: A spec is accepted only if it discriminates

A new spec is **accepted** when at least one model fails at least one of its tests on the calibration run. A spec every model passes is **not hard**, regardless of its label, and is demoted or dropped.

- Why: the current corpus's 10 "hard" specs are labelled hard and scored 0.93 by everyone. The label was never tested. This makes the label a measurement.
- Consequence: the batch must yield at least **7 of 10** discriminating specs to be accepted as a whole. Fewer means the recipe is wrong, not that the threshold should move.

### D4: The acceptance rule, fixed now

The calibration run is **5 models (4 subjects + control) × 10 new specs × 2 repeats = 100 attempts**. The rule is applied to the **new specs only**, so it directly tests them.

Definitions, on the new specs:

- `subject_spread` = highest subject composite − lowest subject composite
- `control_gap` = mean(subject composites) − control composite
- `noise` = `2 × widest subject sd`

**ACCEPT** if any of:

1. `control_gap > max(noise, 0.05)` — the control is separated. This is the same instrument that diagnosed the failure, so passing it is the strongest signal.
2. `subject_spread > 0.10` **and** top-subject `sd ≤ 0.031` — the subjects themselves are spread beyond noise.

**REJECT** otherwise. On reject, the finding is recorded plainly and the next step is a **different difficulty axis** (roadmap 6: instruction-following constraints; or roadmap 8: a new subject type) — **not** more specs of the same kind, and not a lowered threshold.

For scale, the current numbers this rule must beat: `subject_spread` 0.023, `control_gap` 0.011. The rule asks for roughly 4× the current spread, or a control separated by more than the noise floor.

- Why these numbers: 0.05 and 2× are the same thresholds already recorded in run metadata by the previous change, so the two changes judge by one standard. 0.10 is a spread large enough to rank four models with visible gaps. 0.031 is the previous run's `sd > 0.031 → do not report an ordering` line.
- Why pre-registered: the failure mode this project keeps hitting is a number that looks like a finding. Deciding "hard enough" after seeing the numbers is how a benchmark lies to itself.

### D5: Ten original specs, each a novel problem

Each is an original problem rather than a named exercise, so difficulty and contamination are addressed together. None duplicates an existing spec's problem (checked against the 20).

| spec | axis | the discriminator |
| --- | --- | --- |
| `version_range_eval` | parsing, algorithms, validation | semver constraint ranges with correct prerelease precedence |
| `cron_next_run` | time, parsing, algorithms | next-fire computation with ranges, steps, lists and wraparound |
| `unit_conversion_graph` | graphs, numeric, validation | inconsistent and unreachable unit graphs, not just a conversion |
| `interval_map_query` | data-structures, algorithms | overlapping ranges with exact boundary semantics |
| `patch_apply` | parsing, algorithms, strings | unified-diff application with fuzzy offsets and rejects |
| `sql_where_null_logic` | parsing, state-machine, algorithms | SQL three-valued logic, where NULL is the subtle failure |
| `exact_split` | numeric, algorithms, validation | split an amount into parts that preserve the exact total |
| `event_replay` | state, algorithms, validation | idempotency keys and out-of-order event rejection |
| `type_inference` | algorithms, validation | infer types over an expression language with overloads |
| `config_deep_merge` | algorithms, data-structures, validation | deep merge with list-append semantics and conflict detection |

- Each spec ships `spec.json`, `solution.py`, `test_ground_truth.py`, `test_edge_cases.py`, matching the existing layout.
- Alternative considered: reuse famous problems at a harder tier. Rejected — it reproduces the contamination problem the corpus already has, and a model that has memorised the answer does not reveal whether it can solve the problem.

### D6: Comparability — the corpus grows, and the report says so

The corpus goes from 20 to 30 specs. A run over 30 is **not** directly comparable to a run over 20 in the aggregate, and the report must say so rather than silently mixing them.

- The report already records `corpus_count`; the change adds an explicit statement that a different corpus size is not directly comparable.
- Existing runs over 20 specs stay readable and unchanged. They are not re-scored.
- Why: the last three changes each made prior results incomparable and said so plainly. This one is the same, and silence here would be the defect.

### D7: Documentation lands with the code

`docs/roadmap.md` records what the measurement showed (the corpus-credibility item moves out of "planned" and into "what was measured and what it licensed"), and `docs/scoring.md` states that difficulty is a tested property. Same discipline as the last three changes, where each defect was partly a documented behaviour that disagreed with the code.

## Risks / Trade-offs

- [Authoring 10 sound, genuinely-hard specs is real work] → This is the honest cost; the roadmap already calls corpus credibility "the real work". The acceptance rule means a weak batch is caught, not shipped.
- [The style ceiling may keep compressing composites] → Plausible: if new specs drive execution/edge down, the composite drops and the 0.95 cap binds less, but `style` at 0.65–0.76 stays noisy. The calibration measures whether discrimination improved anyway; if execution drops but spread does not, that is itself the finding.
- [2 repeats is thin for a calibration] → Yes, and deliberate: calibration is a screening run, not the final measurement. `sd` is still computable at k=2; a borderline result is re-run at k=3 before acceptance.
- [A novel spec may be unfair rather than hard] → Guarded by D3: the reference must pass both suites (soundness), and the spec must fail a *competent* model, not merely be under-specified. An unfair spec that fails everyone is caught by the same rule and reviewed.
- [The control is a small model, not a weak one] → Already measured: `qwen3.8-flash` scored 0.927 against 0.926–0.949. If it cannot be separated even by genuinely hard specs, that is reported, and the model-bank question reopens (roadmap 10).

## Migration Plan

No migration. The 20 existing specs are untouched and their runs stay readable. Rollback is removing the 10 new spec directories; the corpus returns to 20 and prior runs are again directly comparable.

## Open Questions

- Whether the `style` dimension should be re-weighted is **not** decided here. It is a scoring question and belongs in its own change; this change only measures whether harder specs move the composite spread.
- Whether a rejected batch should pivot to instruction-following constraints (roadmap 6) or a new subject type (roadmap 8) is a decision this change's calibration result licenses — it is not fixed in advance, because the result determines which.
