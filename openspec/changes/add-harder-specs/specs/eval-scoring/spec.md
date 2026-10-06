# Spec Delta

## ADDED Requirements

### Requirement: Corpus size is recorded and comparability is stated

A run's report SHALL state the corpus size it was computed over. When two runs cover different corpus sizes, their aggregates SHALL be marked as not directly comparable, so a reader cannot compare a 20-spec average against a 30-spec average as if the corpus were the same.

#### Scenario: Corpus size is reported

- **WHEN** a report is rendered
- **THEN** the number of specs the run covers is stated in its metadata

#### Scenario: Different sizes are flagged

- **WHEN** a results file covers a different corpus size than a later run
- **THEN** the report states that the aggregates are not directly comparable across the two

#### Scenario: Historical runs stay readable

- **WHEN** a run over the smaller corpus is loaded after the corpus has grown
- **THEN** it remains readable and its own numbers are unchanged
