# Spec Delta

## Purpose

Provides the runnable pipeline and command-line entrypoints that wire the corpus, providers, execution, scoring, and reporting into a single reproducible workflow.

## ADDED Requirements

### Requirement: Command-line entrypoints

The framework SHALL expose commands to list specs, validate the corpus, run an evaluation, and generate a report.

#### Scenario: Commands available

- **WHEN** the CLI help is requested
- **THEN** list-specs, validate, run, and report commands are shown

### Requirement: End-to-end run

The `run` command SHALL load the selected specs, obtain code from each selected model, execute it, score all four dimensions, detect disagreements, and persist machine-readable results.

#### Scenario: Full pipeline completes

- **WHEN** a run is started with a provider and one or more models
- **THEN** a results file is written containing per-(model, spec) scores for all four dimensions

#### Scenario: Subset selection

- **WHEN** the run is given specific spec ids, tiers, or a model list
- **THEN** only those specs and models are evaluated

### Requirement: Offline quickstart

The framework SHALL run end-to-end with no credentials or network using the mock provider, so a new checkout completes a full run in under five minutes of setup.

#### Scenario: Quickstart without credentials

- **WHEN** a fresh checkout runs the documented quickstart using the mock provider
- **THEN** a complete results file and report are produced without any credentials

### Requirement: Exit codes

Commands SHALL exit non-zero when corpus validation fails or when a run is marked inconclusive, and zero on success.

#### Scenario: Validation failure

- **WHEN** corpus validation finds an unsound spec
- **THEN** the command exits non-zero

#### Scenario: Inconclusive run

- **WHEN** a run is marked inconclusive
- **THEN** the command exits non-zero while still writing its results

### Requirement: Stable results schema

Persisted results SHALL include a schema version and enough metadata to regenerate the report without re-running the evaluation.

#### Scenario: Report regenerated from results

- **WHEN** a report is generated solely from a stored results file
- **THEN** it needs no additional data beyond that file
