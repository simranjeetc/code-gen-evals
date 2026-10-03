# Spec Delta

## ADDED Requirements

### Requirement: Corpus size and tier balance

The corpus SHALL contain at least 20 specs, distributed as at least 5 easy, 5 medium, and 10 hard, so that difficulty-stratified comparison has headroom above the easy tiers.

#### Scenario: Corpus meets the minimum

- **WHEN** the corpus is validated
- **THEN** there are at least 20 specs and each tier meets its minimum (easy ≥ 5, medium ≥ 5, hard ≥ 10)

#### Scenario: Tier labels are constrained

- **WHEN** a spec declares a tier other than `easy`, `medium`, or `hard`
- **THEN** corpus validation fails and names the offending spec

### Requirement: Edge suites add failure modes

Each spec's edge-case suite SHALL test strictly more failure modes than its ground-truth suite, so the `edge` dimension measures robustness rather than restating `execution`. No test id may appear in both suites.

#### Scenario: Suites do not overlap

- **WHEN** a spec's two suites are compared
- **THEN** no test id appears in both

#### Scenario: Edge suite adds at least one failure mode

- **WHEN** a spec's edge suite is compared with its ground-truth suite
- **THEN** the edge suite contains at least one test covering a failure mode the ground-truth suite does not exercise

#### Scenario: A naive candidate is caught

- **WHEN** a plausible-but-naive implementation is run against a spec
- **THEN** it fails at least one edge-case test while the reference solution passes both suites

### Requirement: Corpus differentiates the default model bank

The corpus SHALL be strong enough that a run over the default model bank produces at least two distinct composite scores, so a reported ranking reflects measured difference rather than corpus weakness.

#### Scenario: Bank differentiates

- **WHEN** the default model bank is evaluated across the full corpus
- **THEN** the run is not marked inconclusive and at least two models have distinct composites

#### Scenario: Under-powered corpus is detectable

- **WHEN** every model scores identically on every dimension for every spec
- **THEN** the run is marked inconclusive and the CLI exits non-zero

### Requirement: Growth is additive

Adding specs SHALL NOT change any existing spec's prompt, tier, tags, reference solution, or suites, so per-spec scores from earlier runs remain comparable.

#### Scenario: Existing specs are untouched

- **WHEN** the corpus grows
- **THEN** every pre-existing spec produces the same per-spec scores it produced before

#### Scenario: Corpus size is recorded

- **WHEN** a run completes
- **THEN** its metadata records the corpus size and per-tier counts it actually ran
