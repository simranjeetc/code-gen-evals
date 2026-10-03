# Spec Delta

## Purpose

Runs candidate code safely and repeatably against the ground-truth and edge-case suites, converting each attempt into structured pass/fail evidence that the scoring layer can consume.

## ADDED Requirements

### Requirement: Isolated execution

The framework SHALL execute each candidate against its suites in a temporary working directory, in a separate process, under a bounded wall-clock timeout, and MUST NOT depend on network access.

#### Scenario: Candidate runs in a temp directory

- **WHEN** a candidate is executed
- **THEN** it runs in a temporary directory that is removed after the run

#### Scenario: Timeout is enforced

- **WHEN** candidate code blocks for longer than the configured timeout
- **THEN** the process is terminated and the attempt is recorded as a timeout failure

### Requirement: Separate suite runs

The framework SHALL run the ground-truth suite and the edge-case suite as separate executions against the candidate module, so execution and edge-case performance are independently observable.

#### Scenario: Both suites executed

- **WHEN** a candidate is evaluated for a spec
- **THEN** it produces one result set for the ground-truth suite and one for the edge-case suite

### Requirement: Test-level evidence

The framework SHALL capture, per suite, the list of passed and failed test identifiers, the failure messages, and the run duration.

#### Scenario: Failures include messages

- **WHEN** a candidate fails a test
- **THEN** the evidence includes that test's identifier and failure message

### Requirement: Fault containment

A candidate that crashes the interpreter, fails to import, or writes to the working directory SHALL be recorded as a structured failure and MUST NOT abort evaluation of other candidates or specs.

#### Scenario: Import error recorded

- **WHEN** candidate code raises on import
- **THEN** the attempt is recorded with an import error and the remaining candidates still run

#### Scenario: Run continues after a crash

- **WHEN** one candidate crashes its interpreter
- **THEN** subsequent candidates in the same run are still evaluated

### Requirement: Deterministic module contract

The framework SHALL write candidate code to the spec's declared entrypoint module and install the spec's suites so they import the candidate through that entrypoint.

#### Scenario: Suite imports candidate

- **WHEN** a suite runs against a candidate
- **THEN** it imports the candidate via the spec's declared entrypoint module name
