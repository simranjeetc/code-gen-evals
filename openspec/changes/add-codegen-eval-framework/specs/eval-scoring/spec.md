# Spec Delta

## Purpose

Converts raw execution evidence and model output into four independent quality scores, aggregates them across models and task types, and makes disagreements between the dimensions explicit.

## ADDED Requirements

### Requirement: Four independent dimension scores

For every (model, spec) pair the framework SHALL produce four scores in the range 0.0–1.0: execution, semantic, style, and edge-case handling.

#### Scenario: All four dimensions scored

- **WHEN** a model is evaluated on a spec
- **THEN** execution, semantic, style, and edge scores are all present in the result

#### Scenario: Scores are bounded

- **WHEN** any dimension score is produced
- **THEN** it lies within 0.0 and 1.0 inclusive

### Requirement: Execution score

The execution score SHALL be the fraction of ground-truth tests passed by the candidate, and SHALL be zero when code extraction or execution fails.

#### Scenario: Partial pass

- **WHEN** a candidate passes 3 of 4 ground-truth tests
- **THEN** its execution score is 0.75

#### Scenario: Extraction failure

- **WHEN** no code could be extracted
- **THEN** the execution score is 0.0

### Requirement: Edge-case score

The edge-case score SHALL be the fraction of hidden edge-case tests passed by the candidate, and SHALL be computed independently of the ground-truth suite.

#### Scenario: Edge score independent of visible tests

- **WHEN** a candidate passes all ground-truth tests but fails half the edge tests
- **THEN** its execution score is 1.0 and its edge score is 0.5

### Requirement: Semantic score via independent judge

The semantic score SHALL be produced by a judge model distinct from the model under test, using a fixed rubric that returns a score in 0.0–1.0 plus a short rationale, and the judge's identity SHALL be recorded.

#### Scenario: Judge differs from subject

- **WHEN** a spec's semantic score is computed
- **THEN** the recorded judge model differs from the model under test

#### Scenario: Rationale captured

- **WHEN** a semantic score is produced
- **THEN** the result includes the judge's rationale text

### Requirement: Style score

The style score SHALL be computed by a deterministic analyzer over the candidate source, combining configurable checks such as type annotations, docstrings, naming conventions, line length, and cyclomatic complexity, and SHALL optionally incorporate a linter when one is available.

#### Scenario: Style is deterministic

- **WHEN** the same candidate source is scored twice
- **THEN** the style score is identical

#### Scenario: Checks reported

- **WHEN** a style score is produced
- **THEN** the per-check outcomes that produced it are recorded

### Requirement: Aggregation

The framework SHALL aggregate results by model across dimensions, by model across tiers, by model across task types, and produce a weighted composite score whose weights are configurable.

#### Scenario: Model and tier aggregation

- **WHEN** results for a model span multiple specs and tiers
- **THEN** the results include per-dimension averages per tier and an overall composite

#### Scenario: Weights configurable

- **WHEN** composite weights are supplied
- **THEN** the composite is computed with those weights

### Requirement: Disagreement detection

The framework SHALL flag cross-dimension disagreements using configurable thresholds, covering at least: passes tests but fails semantic intent, passes visible tests but fails edge cases, and semantically correct but stylistically poor.

#### Scenario: Green tests, wrong semantics

- **WHEN** execution is high but semantic is below threshold
- **THEN** the pair is flagged as a semantic disagreement with supporting evidence

#### Scenario: Correct but unidiomatic

- **WHEN** execution and semantic are high but style is below threshold
- **THEN** the pair is flagged as a style disagreement with the failing checks

#### Scenario: Fragile pass

- **WHEN** execution is high but edge score is below threshold
- **THEN** the pair is flagged as a fragility disagreement

### Requirement: Degenerate-run guard

The framework SHALL mark a run inconclusive when every model scores identically on all dimensions across all specs (an all-pass or all-fail corpus), and MUST surface this rather than report a differentiated ranking.

#### Scenario: Uniform results detected

- **WHEN** all models score identically on every dimension for every spec
- **THEN** the run is marked inconclusive and the report states the corpus fails to differentiate models
