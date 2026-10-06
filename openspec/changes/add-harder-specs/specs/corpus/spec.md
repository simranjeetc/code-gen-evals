# Spec Delta

## ADDED Requirements

### Requirement: Spec soundness

Every spec SHALL ship a reference solution and two hidden suites (a ground-truth suite and an edge suite), and the reference solution SHALL pass both suites in full. A spec whose reference does not pass its own suites SHALL be reported as unsound and SHALL NOT be counted as a valid measurement of a model.

#### Scenario: Reference passes its own suites

- **WHEN** the corpus is validated
- **THEN** every spec's reference solution passes 100% of its ground-truth and edge tests

#### Scenario: An unsound spec is rejected

- **WHEN** a reference solution fails any of its own tests
- **THEN** validation fails and names the spec, so a broken spec cannot be presented as a hard one

#### Scenario: Both suites are required

- **WHEN** a spec is loaded
- **THEN** it has a ground-truth suite and an edge suite, and neither is empty

### Requirement: Difficulty is an acceptance criterion, not a label

A spec's difficulty tier SHALL be a claim that is tested, not a label applied at authoring time. A new spec SHALL be accepted only when its hidden suites actually fail competent models: a spec that every model passes is not hard, regardless of how it is labelled.

#### Scenario: A spec every model passes is not hard

- **WHEN** a new spec is calibrated and every model passes all of its tests
- **THEN** it is reported as non-discriminating and does not count toward the hard tier

#### Scenario: A spec that fails a competent model counts

- **WHEN** a new spec is calibrated and at least one model fails at least one of its tests
- **THEN** it is reported as discriminating and counts as a hard spec

#### Scenario: Difficulty is recorded with evidence

- **WHEN** a spec is labelled with a tier
- **THEN** the tier is supported by an observed calibration result rather than an authoring judgement alone

### Requirement: Batch acceptance rule

A batch of new specs SHALL be judged by a rule fixed **before** the calibration run. The rule SHALL state what counts as a batch that improves discrimination, and the batch SHALL be accepted only when the observed result meets that rule. The rule and the observed result SHALL both be recorded.

#### Scenario: Rule is fixed in advance

- **WHEN** a new spec batch is proposed
- **THEN** the acceptance rule and its thresholds are recorded before any calibration result exists

#### Scenario: Batch is accepted on evidence

- **WHEN** a calibration run meets the pre-registered rule
- **THEN** the batch is accepted, and the rule and the observed figures are recorded together

#### Scenario: Batch that does not discriminate is reported, not hidden

- **WHEN** a calibration run does not meet the pre-registered rule
- **THEN** the batch is reported as not improving discrimination, and the result is stated plainly rather than the threshold being moved

### Requirement: New specs are original problems

A new spec added to raise difficulty SHALL be an original problem rather than a restatement of a well-known exercise, so that difficulty and uncontrolled training-data contamination are addressed together. A spec that duplicates an existing spec's problem SHALL be rejected as redundant.

#### Scenario: Original rather than memorised

- **WHEN** a new spec is authored
- **THEN** it states a problem that is not a standard named exercise, so a model cannot succeed by recalling a known solution

#### Scenario: Duplicates are rejected

- **WHEN** a new spec restates the problem of a spec already in the corpus
- **THEN** it is rejected, because it adds no new measurement

#### Scenario: Tags describe the new axis

- **WHEN** a new spec is added
- **THEN** its tags name the skill it exercises, so its contribution is visible in the task-type breakdown
