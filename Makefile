PY ?= .venv/bin/python
PYTHON ?= python3
RESULTS ?= reports/results-mock.json
REPORT ?= reports/report-mock.md

.PHONY: help install validate list-specs run-mock report test quickstart clean

help:
	@echo "make install     create .venv and install the package with dev deps"
	@echo "make validate    run every reference solution against both suites"
	@echo "make list-specs  list the corpus with tiers and tags"
	@echo "make run-mock    full offline pipeline run with the mock provider"
	@echo "make report      re-render the report from $(RESULTS)"
	@echo "make test        run the framework test suite"
	@echo "make quickstart  install + validate + run-mock + report"

install:
	$(PYTHON) -m venv .venv
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -e ".[dev]"

validate:
	$(PY) -m codegen_evals.cli validate

list-specs:
	$(PY) -m codegen_evals.cli list-specs

run-mock:
	$(PY) -m codegen_evals.cli run --provider mock --out $(RESULTS)

report:
	$(PY) -m codegen_evals.cli report --in $(RESULTS) --out $(REPORT)

test:
	$(PY) -m pytest -q

quickstart: install validate run-mock report

clean:
	rm -rf .venv reports/*.json reports/*.md
