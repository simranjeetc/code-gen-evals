# code-execution Specification

## Purpose
TBD - created by archiving change separate-harness-failures. Update Purpose after archive.

## Requirements

### Requirement: Attempt outcome classification

Every evaluation attempt SHALL be recorded with an explicit outcome. A scored attempt is distinct from an infrastructure failure, and both are distinct from a model that produced code which failed the tests.

#### Scenario: Scored attempt

- **WHEN** a model returns code and it is executed
- **THEN** the result is recorded as scored

#### Scenario: Provider failure is classified

- **WHEN** a provider times out, exits non-zero, or returns an error
- **THEN** the result is recorded with the matching outcome (`timeout`, `provider_error`) and the provider's message, and not as a score of zero

#### Scenario: Unusable output is classified

- **WHEN** a response cannot be turned into runnable code
- **THEN** the result is recorded as `unparseable_output`, distinct from a provider failure

#### Scenario: Partial coverage is visible

- **WHEN** a model is evaluated over the corpus
- **THEN** the count of excluded attempts and the count of scored attempts are both reported

### Requirement: Infrastructure failures are excluded from aggregates

Aggregates SHALL be computed over scored attempts only. An infrastructure failure MUST NOT contribute a `0.0` to any model's average, and the exclusion count SHALL be reported alongside the average.

#### Scenario: Failure does not deflate an average

- **WHEN** a model's results include an infrastructure failure
- **THEN** the model's per-dimension averages are computed without it, and the excluded count is reported

#### Scenario: Failures are still visible

- **WHEN** a run contains infrastructure failures
- **THEN** they appear in the report with their outcome and message, so they are excluded from aggregates but not hidden

#### Scenario: Recomputing by hand agrees

- **WHEN** excluded results are removed and aggregates recomputed independently
- **THEN** the reported averages match

### Requirement: Retry transient failures

The framework SHALL retry an attempt that failed for a transient reason (timeout, provider error) at least once with a longer budget before recording it as a failure. A retry that succeeds SHALL be recorded as scored, with the retry noted.

#### Scenario: Timeout is retried

- **WHEN** an attempt times out
- **THEN** it is retried once with a longer budget before being recorded as a failure

#### Scenario: Successful retry is recorded

- **WHEN** a retry succeeds
- **THEN** the result is scored and metadata notes that a retry was needed

#### Scenario: Retries are bounded

- **WHEN** an attempt fails on every permitted try
- **THEN** it is recorded as an infrastructure failure and no further attempts are made

### Requirement: Exclusion-rate guard

A run SHALL be marked `unreliable` when the share of a model's attempts that failed for infrastructure reasons exceeds a configurable fraction. Affected models SHALL be named, so a run cannot present a harness failure as a weak model.

#### Scenario: High exclusion rate flags the run

- **WHEN** the exclusion rate for a model exceeds the configured fraction
- **THEN** the run is marked unreliable and that model is flagged

#### Scenario: Low exclusion rate does not flag

- **WHEN** every model's exclusion rate is below the configured fraction
- **THEN** the run is not marked unreliable

#### Scenario: Unreliable runs still persist

- **WHEN** a run is marked unreliable
- **THEN** its results are still written, with the flag and the reasons recorded

#### Scenario: Distinct from the degenerate guard

- **WHEN** a run's models all score identically
- **THEN** the existing degenerate guard applies, independently of the exclusion-rate guard

### Requirement: Fault containment and harness-failure distinction

A candidate that crashes the interpreter, fails to import, or writes to the working directory SHALL be recorded as a structured failure and MUST NOT abort evaluation of other candidates or specs. A crash inside the sandbox is a **scored** result and SHALL NOT be classified as an infrastructure failure.

#### Scenario: Import error recorded

- **WHEN** candidate code raises on import
- **THEN** the attempt is recorded with an import error as a scored result, and the remaining candidates still run

#### Scenario: Run continues after a crash

- **WHEN** one candidate crashes its interpreter
- **THEN** subsequent candidates in the same run are still evaluated

#### Scenario: Sandbox crash is not a harness failure

- **WHEN** candidate code is executed and fails
- **THEN** the outcome is scored, because the harness worked and the model's code did not

#### Scenario: Harness crash is a harness failure

- **WHEN** the runner itself fails to start, or the provider cannot be reached
- **THEN** the attempt is recorded as an infrastructure failure and excluded from aggregates
