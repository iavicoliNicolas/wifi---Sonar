PY ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: dev test lint

$(BIN)/pytest: pyproject.toml
	$(PY) -m venv $(VENV)
	$(BIN)/python -m pip install -U pip
	$(BIN)/pip install -e ".[dev]"

dev: $(BIN)/pytest

test: $(BIN)/pytest
	$(BIN)/pytest

lint: $(BIN)/pytest
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .
