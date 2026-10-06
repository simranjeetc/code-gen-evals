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

### Requirement: Repeated attempts are recorded per repeat

Each `(model, spec)` pair SHALL be attempted a configured number of times. Every attempt SHALL carry a repeat index, and attempts for the same pair at different repeats SHALL be recorded as distinct attempts rather than merged. The configured repeat count SHALL be recorded with the run.

#### Scenario: Repeat index is recorded

- **WHEN** a spec is evaluated k times for a model
- **THEN** k attempts exist for that pair, each with a distinct repeat index

#### Scenario: Default is a single attempt

- **WHEN** no repeat count is configured
- **THEN** each pair is attempted once, and the run behaves as before

#### Scenario: Repeat count is self-describing

- **WHEN** a run is saved
- **THEN** the repeat count used is present in its metadata

### Requirement: Stability is reported per model and per spec

Aggregates SHALL report the spread of repeated attempts, not only their mean. Per model and per spec, the framework SHALL report the mean, minimum, maximum and standard deviation of the composite across repeats. A report SHALL distinguish a model whose scores are repeatable from one whose scores vary.

#### Scenario: Model stability is reported

- **WHEN** a model has multiple repeats
- **THEN** its aggregate includes mean, min, max and standard deviation

#### Scenario: An unstable spec is visible

- **WHEN** repeats of one spec vary widely for a model
- **THEN** the per-spec view shows that spread rather than hiding it in an average

#### Scenario: Single repeat is not claimed as stable

- **WHEN** a model has only one repeat per spec
- **THEN** the report states that variance was not measured, rather than showing a zero spread as evidence of stability

### Requirement: Variance guard

A run SHALL be marked `unstable` when a model's within-model standard deviation exceeds a configurable threshold. The guard SHALL state the threshold and the affected models, and SHALL state plainly that a gap smaller than roughly twice the standard deviation is not distinguishable from noise. The guard SHALL be independent of the degenerate and exclusion-rate guards.

#### Scenario: High variance flags the run

- **WHEN** a model's composite standard deviation exceeds the configured threshold
- **THEN** the run is marked unstable and that model is named

#### Scenario: Low variance does not flag

- **WHEN** every model's standard deviation is below the threshold
- **THEN** the run is not marked unstable

#### Scenario: Guards are independent

- **WHEN** a run is unstable but not degenerate and not unreliable
- **THEN** only the variance guard fires, and the reason names variance

#### Scenario: Unstable runs still persist

- **WHEN** a run is marked unstable
- **THEN** its results are still written with the flag and the reason

### Requirement: Repetition is named honestly

The framework SHALL report stability across repeated attempts and MUST NOT describe that figure as `pass@k`, which measures whether an attempt passed at least once within k tries. The two questions are different, and conflating them SHALL be avoided in data, CLI output and reports.

#### Scenario: Report does not claim pass@k

- **WHEN** a report describes repeated attempts
- **THEN** it describes repeat stability and does not label the figure `pass@k`

#### Scenario: Meaning is stated

- **WHEN** stability is reported
- **THEN** the report states that it measures repeatability, not how often the model eventually succeeds

### Requirement: Deliberately weak control in the model bank

The framework SHALL support a deliberately weak control model in a run, so the corpus's ability to discriminate is measured rather than assumed. When a control model is present, the report SHALL state whether the corpus separated it from the other models.

#### Scenario: Control is separated

- **WHEN** a control model scores materially below the other models
- **THEN** the report states that the corpus discriminates, and that a narrow spread among the remaining models is a property of the bank rather than the corpus

#### Scenario: Control is not separated

- **WHEN** a control model scores within the spread of the other models
- **THEN** the report states that the corpus did not separate it, so the corpus cannot discriminate and the model bank is not the limiting factor

#### Scenario: Absent control is not silently ignored

- **WHEN** no control model is present in a run
- **THEN** the report states that the corpus's ability to discriminate was not measured
