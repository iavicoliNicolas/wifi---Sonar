.PHONY: dev test lint format

PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

dev: $(BIN)/pytest

$(BIN)/pytest: pyproject.toml
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install -U pip
	$(BIN)/python -m pip install -e ".[dev]"

test: $(BIN)/pytest
	$(BIN)/python -m pytest

lint: $(BIN)/pytest
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format: $(BIN)/pytest
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .
