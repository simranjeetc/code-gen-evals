# Proposal

## Why

A harness failure and a model failure are currently indistinguishable. When a provider times out, exits non-zero, or errors, the result is scored `0.0` on every dimension — exactly what a model that produced bad code scores. This was observed in practice: a four-model run over the full corpus reported a composite spread of `0.11`, which collapsed to `0.035` once three infrastructure failures were removed by hand. The headline result was an artefact of the harness.

This is the third instance of the same defect class in this project, after the judge that silently abstained for 40 of 40 results and the timeout recorded as model weakness. In every case a failure was rendered as a confident number. Fixing them one at a time is not working; this change also adds a guard that makes the class visible.

## What Changes

- **Classify every non-scoring result.** A result is either scored, or recorded with an explicit outcome: `timeout`, `provider_error`, `unparseable_output`, or `not_attempted`. Each carries the provider message.
- **Exclude infrastructure failures from aggregates.** They are counted, reported, and never averaged in as zeros. Per-model aggregates report how many results were excluded, so a model is not credited or penalised for the harness failing.
- **Retry transient failures.** A timeout or provider error is retried once with a longer budget before being recorded as a failure.
- **Raise the default provider timeout.** 180s was too tight for large hard specs; two of three observed failures were timeouts on the same model.
- **Add an exclusion-rate guard.** When more than a configured fraction of a model's results are infrastructure failures, the run is marked `unreliable` and the affected models are flagged, so a run cannot silently present a low score that is really a broken harness.
- **Distinguish this from the existing degenerate guard.** The existing guard catches "all models scored identically"; this one catches "the scores are not all measurements".

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `code-execution`: gains an outcome classification for non-scoring attempts, and a retry policy.
- `eval-scoring`: aggregates exclude infrastructure failures, report exclusion counts, and gain an exclusion-rate guard alongside the existing degenerate-run guard.
- `eval-reporting`: surfaces infrastructure failures and exclusion counts prominently rather than burying them.

## Impact

- `models.py` — a new outcome field on `EvalResult`, with schema version bump.
- `providers/*` — timeouts and exit errors classified rather than returned as empty generations.
- `pipeline.py` — retry policy, raised default timeout.
- `scoring/aggregate.py` — exclusion-aware aggregation and the new guard.
- `reporting.py` — a reliability section.
- **Schema version bump makes old results explicitly stale.** Same cost as the judge change, and stated for the same reason.
- Runs get slower when retries trigger, bounded by one extra attempt per failure.
