SHELL := bash

PYTHON_VERSION := 3.12

.PHONY: install-python
install-python:
	@echo "Checking and installing Python $(PYTHON_VERSION)..."
	@if uv python find $(PYTHON_VERSION) &>/dev/null; then \
		uv python install $(PYTHON_VERSION); \
	fi

.PHONY: init
init: install-python
	@echo "Initializing the python virtual environment..."
	@echo "This may take a while, please be patient..."
	@if [[ ! -d ".venv" ]]; then \
		uv venv --python=$(PYTHON_VERSION); \
	fi
	@uv sync --all-extras --all-groups

.PHONY: dev
dev: init
	@echo "Setting up development environment..."
	@echo "Installing pre-commit hooks and sample configuration..."
	@if [[ ! -f ".git/hooks/pre-commit" ]]; then \
		uv run pre-commit install; \
	fi
	@if [[ ! -f ".pre-commit-config.yaml" ]]; then \
		uv run pre-commit sample-config > .pre-commit-config.yaml; \
	fi

	@echo "Development environment setup complete."
	@echo "To run linting, use 'make lint'."
	@echo "To format code, use 'make fmt'."

.PHONY: lint
lint:
	uv run black --check --diff --color .
	uv run isort --check-only --diff --color .
	uv run ruff check .

.PHONY: fmt
fmt:
	uv run black .
	uv run isort .
	uv run ruff check --fix .

.PHONY: run
run:
	uv run ipinfo_lite.py
