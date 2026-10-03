# Setup

## Requirements

- Python 3.9 or newer
- No model credentials required for the default quickstart

## Install

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
```

Verify:

```bash
.venv/bin/python -c "import codegen_evals; print(codegen_evals.__version__)"
```

## Quickstart (no credentials, no network)

The `mock` provider is deterministic and offline. It exercises the entire
pipeline — corpus, execution, scoring, and report — without calling any model.

```bash
.venv/bin/python -m codegen_evals.cli validate
.venv/bin/python -m codegen_evals.cli run --provider mock --out reports/results-mock.json
.venv/bin/python -m codegen_evals.cli report --in reports/results-mock.json --out reports/report-mock.md
```

A mock run is a pipeline check, not a model comparison; the report labels it
as such.

## Real models (OpenCode)

Real runs reuse the locally installed OpenCode models and need no extra keys.
This requires the `opencode` CLI on `PATH` and an authenticated OpenCode
installation.

```bash
.venv/bin/python -m codegen_evals.cli run --provider opencode --out reports/results.json
```

The generation call is pinned to the project agent `.opencode/agents/codegen-eval.md`,
which disables every tool and sets `temperature: 0`, so the model produces a
bare code block rather than acting on the repository.

## Public-API providers (optional)

Provide credentials in the environment to enable the hosted backends:

| Provider | Variable |
| --- | --- |
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Together (Llama) | `TOGETHER_API_KEY` |

Selecting a provider without its credential fails with a message naming the
missing variable; it never falls back silently.
