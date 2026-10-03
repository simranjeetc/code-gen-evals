# Spec Delta

## Purpose

Provides a uniform way to obtain code from many models so the same corpus can be scored against a configurable model bank, including an offline mode and optional public-API backends.

## ADDED Requirements

### Requirement: Common provider contract

Every provider SHALL accept a rendered prompt plus a model identifier and return a structured result containing the raw response text, the extracted code (if any), the model identifier, wall-clock duration, and any error.

#### Scenario: Uniform result shape

- **WHEN** any provider completes a generation request
- **THEN** it returns raw text, extracted code or an extraction failure, model id, duration, and error field

#### Scenario: Provider failure is contained

- **WHEN** a provider call raises, times out, or returns an HTTP error
- **THEN** the failure is captured in the result's error field and does not abort the overall run

### Requirement: OpenCode Go provider

The framework SHALL provide a default provider that generates code through locally available OpenCode models using the OpenCode Go subscription, invoking a tools-disabled agent, with the model identifier configurable.

#### Scenario: Default provider generates code

- **WHEN** the run uses the OpenCode provider with a configured OpenCode Go model
- **THEN** a code block is returned without the model invoking file or shell tools

#### Scenario: Model bank is configurable

- **WHEN** the run is given a list of model identifiers
- **THEN** each model is evaluated against the full selected corpus

### Requirement: Offline mock provider

The framework SHALL provide a deterministic mock provider that requires no network or credentials, so the pipeline runs end-to-end offline and produces stable per-spec outputs.

#### Scenario: Offline run succeeds

- **WHEN** the run uses the mock provider with no credentials present
- **THEN** the pipeline completes and produces results for every selected spec

#### Scenario: Mock is deterministic

- **WHEN** the mock provider is invoked twice with the same prompt and model id
- **THEN** it returns identical code

### Requirement: Optional public-API providers

The framework SHALL support Anthropic, OpenAI, and Together (for Llama-family models) backends when their credentials are supplied, and MUST fail clearly, naming the missing credential, when a requested provider is not configured.

#### Scenario: Backend used when configured

- **WHEN** a public-API provider is selected and its credential is present
- **THEN** the provider is used like any other backend

#### Scenario: Missing credential is explained

- **WHEN** a public-API provider is selected without its credential
- **THEN** the run reports which environment variable is missing and does not silently fall back

### Requirement: Code extraction

The framework SHALL extract a single code block from a model response, preferring the first fence tagged as Python (`python`, `python3`, `py`) and otherwise falling back to the first untagged fence. When no such block exists — including when every fence carries a non-Python language tag — it SHALL record an extraction failure and score that response's execution and edge dimensions as zero without terminating the run.

#### Scenario: Python-tagged block extracted

- **WHEN** a response contains a fenced ```python block
- **THEN** that block's contents are used as the candidate code

#### Scenario: Untagged fence is accepted

- **WHEN** a response contains only an untagged fenced block
- **THEN** that block's contents are used as the candidate code

#### Scenario: Non-Python fence is rejected

- **WHEN** the only fenced block in a response is tagged with a non-Python language
- **THEN** the result records an extraction failure

#### Scenario: No code block present

- **WHEN** a response contains no fenced block at all
- **THEN** the result records an extraction failure and the spec is scored zero for execution and edge

### Requirement: Reproducible invocation

Each generation request SHALL record the provider, model id, and generation parameters, and the framework SHALL expose a temperature setting so runs can be repeated deterministically where the backend supports it.

#### Scenario: Invocation metadata recorded

- **WHEN** a generation completes
- **THEN** provider, model id, and generation parameters are stored with the result
