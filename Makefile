PY ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: dev test lint

$(VENV)/.installed: pyproject.toml
	$(PY) -m venv $(VENV)
	$(BIN)/python -m pip install -U pip
	$(BIN)/pip install -e ".[dev]"
	touch $(VENV)/.installed

dev: $(VENV)/.installed

test: $(VENV)/.installed
	$(BIN)/pytest

lint: $(VENV)/.installed
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .
