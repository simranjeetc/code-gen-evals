# eval-scoring Specification

## Purpose
TBD - created by archiving change anchor-semantic-judge. Update Purpose after archive.

## Requirements

### Requirement: Reference-anchored semantic scoring

The semantic judge SHALL be given the spec's reference solution alongside the candidate and SHALL be asked to compare the candidate against that reference, rather than to invent an absolute standard. The judge prompt SHALL include a worked example for each score band so the bands are defined rather than inferred.

#### Scenario: Judge receives the reference

- **WHEN** a semantic score is produced
- **THEN** the judge prompt contains the requirement, the reference solution, and the candidate

#### Scenario: Judge is asked to compare, not invent

- **WHEN** the judge prompt is rendered
- **THEN** it frames the task as a comparison against the given reference rather than an absolute rating

#### Scenario: Bands are defined

- **WHEN** the judge prompt is rendered
- **THEN** it contains a concrete example of a 1.0, a 0.5, and a 0.0 outcome

#### Scenario: Rubric is stable

- **WHEN** two reference-anchored judge calls are made for the same inputs
- **THEN** the prompt is byte-identical, so any score difference is judge variance and not prompt variance

### Requirement: Judge agreement measurement

The framework SHALL measure agreement between two different judge models over the same reference solutions and SHALL record the resulting figure with the run, so the reliability of the semantic dimension is disclosed rather than assumed.

#### Scenario: Agreement is measured

- **WHEN** judge agreement is measured
- **THEN** at least two distinct judge models each score the same set of reference solutions and an agreement figure is recorded

#### Scenario: Agreement is reported

- **WHEN** a report is generated for a run whose agreement figure is known
- **THEN** the figure appears next to the semantic dimension

#### Scenario: Agreement is unknown

- **WHEN** no agreement figure has been measured
- **THEN** the report says so explicitly rather than omitting the question

### Requirement: Semantic score via independent reference-anchored judge

The semantic score SHALL be produced by a judge model distinct from the model under test, using a fixed reference-anchored rubric that returns a score in 0.0–1.0 plus a short rationale, and the judge's identity SHALL be recorded. The score SHALL be marked as judge-derived in every result and report.

#### Scenario: Judge differs from subject

- **WHEN** a spec's semantic score is computed
- **THEN** the recorded judge model differs from the model under test

#### Scenario: Rationale captured

- **WHEN** a semantic score is produced
- **THEN** the result includes the judge's rationale text

#### Scenario: Score is marked as derived

- **WHEN** a semantic score appears in a result file or a report
- **THEN** it is labelled as produced by a judge model rather than measured

### Requirement: Aggregation over objective dimensions

The framework SHALL aggregate results by model across dimensions, by model across tiers, by model across task types, and SHALL produce a composite score over the **objective** dimensions only, whose weights are configurable. The semantic dimension SHALL be carried alongside the composite and MUST NOT be blended into it.

#### Scenario: Model and tier aggregation

- **WHEN** results for a model span multiple specs and tiers
- **THEN** the results include per-dimension averages per tier and an overall composite

#### Scenario: Weights configurable

- **WHEN** composite weights are supplied
- **THEN** the composite is computed with those weights over objective dimensions only

#### Scenario: Semantic is not blended

- **WHEN** a composite is computed
- **THEN** changing a semantic score does not change the composite

#### Scenario: Semantic is still reported

- **WHEN** a composite is computed
- **THEN** the semantic score and its abstentions are still present and visible alongside it
