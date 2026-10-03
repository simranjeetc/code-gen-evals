# Spec Delta

## Purpose

Turns machine-readable results into a human-readable report that compares models, explains each eval method and its limitations, and surfaces disagreements instead of hiding them behind a single score.

## ADDED Requirements

### Requirement: Offline report generation

The framework SHALL generate a Markdown report from a saved results file without network access.

#### Scenario: Report from stored results

- **WHEN** a report is generated from a results file
- **THEN** it is written as Markdown with no outbound calls

### Requirement: Method explanation and limitations

The report SHALL explain each of the four eval methods and MUST document the known limitations of each, including at least: tests cover only what they assert, LLM judges carry bias, style checks are heuristics, and edge suites are finite.

#### Scenario: Each method documented

- **WHEN** the report is generated
- **THEN** it contains a section describing execution, semantic, style, and edge-case methods and their limitations

### Requirement: Model comparison matrices

The report SHALL present per-dimension comparisons across models, per-tier comparisons across models, and an overall composite ranking.

#### Scenario: Dimension and tier matrices present

- **WHEN** the report is generated
- **THEN** it includes a model-by-dimension table and a model-by-tier table

### Requirement: Strengths and weaknesses by task type

The report SHALL summarize each model's strongest and weakest task types based on the spec tags.

#### Scenario: Per-model task-type summary

- **WHEN** the report is generated
- **THEN** each model has a short strengths and weaknesses summary derived from its task-type scores

### Requirement: Disagreement reporting

The report SHALL include the flagged disagreements from scoring, listing the model, spec, dimensions involved, and supporting evidence.

#### Scenario: Disagreements listed with evidence

- **WHEN** the run flagged disagreements
- **THEN** each is listed with its model, spec, dimensions, and evidence

### Requirement: Reproducibility metadata

The report SHALL record the models evaluated, the provider used, the corpus size and tier counts, generation parameters, and the run timestamp.

#### Scenario: Metadata present

- **WHEN** the report is generated
- **THEN** it states the models, provider, corpus counts, parameters, and timestamp
