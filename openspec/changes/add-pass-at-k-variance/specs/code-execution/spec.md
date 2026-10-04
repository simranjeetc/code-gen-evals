# Spec Delta

## ADDED Requirements

### Requirement: Attempt repeats are isolated

Each repeat of a `(model, spec)` pair SHALL be an independent attempt: its own generation, its own execution and its own outcome classification. A retry of a transient failure SHALL occur within a repeat and MUST NOT be recorded as an additional repeat. One repeat failing SHALL NOT prevent the other repeats of the same pair from running.

#### Scenario: Repeats are independent attempts

- **WHEN** a pair is attempted k times
- **THEN** each attempt generates and executes independently of the others

#### Scenario: Retry stays inside its repeat

- **WHEN** an attempt times out and is retried under the retry policy
- **THEN** the retry is recorded as the same repeat, not as an extra repeat

#### Scenario: One failed repeat does not stop the others

- **WHEN** one repeat of a pair is an infrastructure failure
- **THEN** the remaining repeats still run, and the failure is excluded from the mean as before

#### Scenario: Outcome and exclusion apply per attempt

- **WHEN** repeats of one pair have different outcomes
- **THEN** each attempt is classified on its own, and only scored attempts contribute to stability statistics
