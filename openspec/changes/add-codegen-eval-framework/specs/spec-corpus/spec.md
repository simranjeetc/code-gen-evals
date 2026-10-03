# Spec Delta

## Purpose

Defines the corpus of code-generation specs — their tiers, task types, reference solutions, and hidden ground-truth and edge-case suites — so that model quality is measured against fixed, verifiable targets.

## ADDED Requirements

### Requirement: Minimum corpus size and tier balance

The corpus SHALL contain at least 15 specs, distributed as at least 5 easy, 5 medium, and 5 hard, so that difficulty-stratified comparison is possible.

#### Scenario: Corpus meets the minimum

- **WHEN** the corpus is validated
- **THEN** there are at least 15 specs and each tier contains at least 5 specs

#### Scenario: Tier labels are constrained

- **WHEN** a spec declares a tier other than `easy`, `medium`, or `hard`
- **THEN** corpus validation fails and names the offending spec

### Requirement: Spec definition

Each spec SHALL declare a unique id, a tier, one or more task-type tags, the natural-language prompt shown to the model, the entrypoint module name, and the public symbols the solution must expose.

#### Scenario: Spec metadata is complete

- **WHEN** a spec is loaded
- **THEN** it exposes id, tier, tags, prompt, entrypoint, and required symbols

#### Scenario: Duplicate or missing id

- **WHEN** two specs share an id, or a spec omits its id
- **THEN** corpus validation fails and identifies the duplicate or missing id

### Requirement: Reference solution with passing ground-truth suite

Each spec SHALL ship a reference solution and a pytest ground-truth suite that passes against that reference, so the spec is provably satisfiable.

#### Scenario: Reference passes its own suite

- **WHEN** a spec's reference solution is executed against its ground-truth suite
- **THEN** every ground-truth test passes

#### Scenario: Broken reference is detected

- **WHEN** a reference solution fails its ground-truth suite
- **THEN** corpus validation fails and reports which tests failed

### Requirement: Hidden edge-case suite

Each spec SHALL ship an edge-case suite, separate from the ground-truth suite, that exercises boundary inputs, empty inputs, error paths, and type extremes, and it MUST NOT be shown to the model.

#### Scenario: Edge suite exists and is distinct

- **WHEN** a spec is loaded
- **THEN** it has an edge-case suite whose test ids do not overlap the ground-truth suite

#### Scenario: Edge suite is not leaked in the prompt

- **WHEN** the model-facing prompt for a spec is rendered
- **THEN** it contains no edge-case test code, test ids, or reference-solution source

### Requirement: Prompt isolation

The model-facing prompt SHALL contain only the requirement description and its declared deliverable contract, and MUST NOT contain reference implementations, test source, or expected outputs.

#### Scenario: Prompt excludes solutions and tests

- **WHEN** any spec prompt is rendered
- **THEN** it contains no reference-solution source and no test assertions

### Requirement: Corpus self-validation

The CLI SHALL provide a validation operation that runs every reference solution against both its ground-truth and edge-case suites and reports any spec whose reference does not pass.

#### Scenario: All specs are sound

- **WHEN** corpus validation runs on a healthy corpus
- **THEN** it reports every spec as passing and exits successfully

#### Scenario: Unsound spec is reported

- **WHEN** a reference solution fails any of its suites
- **THEN** validation lists the spec and the failing tests and exits non-zero
