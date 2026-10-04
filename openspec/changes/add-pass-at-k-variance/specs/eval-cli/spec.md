# Spec Delta

## ADDED Requirements

### Requirement: Repeats are selectable from the command line

The `run` command SHALL accept a repeat count and a verbosity flag. The repeat count SHALL default to one so existing behaviour is unchanged unless repetition is requested. The resolved repeat count SHALL be shown in the run summary.

#### Scenario: Repeat count is honoured

- **WHEN** the command is invoked with a repeat count of three
- **THEN** every pair is attempted three times

#### Scenario: Default preserves existing behaviour

- **WHEN** no repeat count is given
- **THEN** each pair is attempted once

#### Scenario: Resolved count is reported

- **WHEN** a run finishes
- **THEN** the summary states how many repeats were used

### Requirement: Run logging explains a run without being verbose

A normal run SHALL produce quiet, self-explanatory output: one summary line per model at the end and a one-line reason whenever a guard fires. Per-attempt progress SHALL be suppressed by default and shown only under a verbosity flag. Every log line SHALL identify enough context to be understood on its own.

#### Scenario: Default output is a summary

- **WHEN** a run completes without the verbosity flag
- **THEN** at most one line per model is printed, plus any guard reasons

#### Scenario: Verbose output shows each attempt

- **WHEN** a run is invoked with the verbosity flag
- **THEN** each attempt logs a line identifying the model, the spec, the repeat index, the outcome and the resulting composite

#### Scenario: Guard reasons are readable

- **WHEN** a guard fires
- **THEN** a single line states which guard, which model, the observed value and the threshold

#### Scenario: Logs are quiet by default but complete when read

- **WHEN** a reader looks at the tail of a default run's log
- **THEN** it is possible to tell which models ran, each model's mean, each model's spread, and whether any guard fired
