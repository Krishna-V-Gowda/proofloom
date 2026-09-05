SYSTEM_PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
PYTHON := $(if $(wildcard $(BIN)/python),$(BIN)/python,$(SYSTEM_PYTHON))
HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: setup test seed demo evaluate benchmark security validate run clean

setup:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -r requirements-lock.txt
	$(BIN)/python -m pip install --no-deps -e .

test:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src $(PYTHON) -m pytest -q -p no:cacheprovider

seed:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src $(PYTHON) -m proofloom.cli export-data --output data/demo

demo:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src $(PYTHON) -m proofloom.cli demo

evaluate:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src $(PYTHON) -m proofloom.cli evaluate --output evaluation --bootstrap-resamples 500

benchmark:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src $(PYTHON) -m proofloom.cli benchmark --output benchmarks

security:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/verify_public_tree.py .

validate:
	bash scripts/validate_release.sh

run:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src $(PYTHON) -m proofloom.cli serve --host $(HOST) --port $(PORT)

clean:
	rm -rf $(VENV) build dist .pytest_cache .mypy_cache .ruff_cache htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
