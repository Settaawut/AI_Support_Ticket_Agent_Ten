PY ?= python

.PHONY: install test lint format typecheck run run-offline eval eval-offline check

install:
	$(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

format:
	$(PY) -m ruff format .
	$(PY) -m ruff check --fix .

typecheck:
	$(PY) -m mypy

check: lint typecheck test

run:
	$(PY) -m triage run --all

run-offline:
	$(PY) -m triage run --all --offline

eval:
	$(PY) -m eval.run_eval

eval-offline:
	$(PY) -m eval.run_eval --offline
