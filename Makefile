# Makefile for easy development workflows.
# See docs/development.md for docs.
# Note GitHub Actions call uv directly, not this Makefile.

# A phony target is a target that is not a file. It is used to define commands that should always be executed, regardless of whether a file with the same name exists.
# This is useful for commands like `make clean`, `make install`, etc., which do not produce an output file.
.PHONY: help install test lint format check clean build

# .DEFAULT_GOAL is the target that will be executed when `make` is run without any arguments.
.DEFAULT_GOAL := help

# Display help
help:
	@echo "Available commands:"
	@echo "  install     - Install dependencies"
	@echo "  dev-setup   - Complete development setup"
	@echo "  upgrade     - Upgrade dependencies"
	@echo "  test        - Run tests"
	@echo "  lint        - Run linter and formatter"
	@echo "  check       - Run all checks (lint + type + format)"
	@echo "  clean       - Clean build artifacts"
	@echo "  build       - Build package"

# Install dependencies
install:
	uv sync

# set up development environment
dev-setup: install
	uv sync --all-extras --dev
	uv pip install -e .
	@echo "Development environment ready!"

# Upgrade dependencies
upgrade:
	uv sync --upgrade

# Run tests
test:
	uv run pytest

# Run linter
lint:
	uv run devtools/lint.py

# Run all quality checks
check:
	uv run ruff check src/
	uv run ruff format src/ --check
	uv run ty check src/

# Check-only lint, matching CI (does not modify files).
lint-check:
	uv run python devtools/lint.py --check
# Clean build artifacts
clean:
	-rm -rf dist/
	-rm -rf *.egg-info/
	-rm -rf .pytest_cache/
	-rm -rf .ruff_cache/
	-rm -rf .mypy_cache/
	-rm -rf .venv/
	-find . -type d -name "__pycache__" -exec rm -rf {} +

# Build package
build: clean
	uv build
