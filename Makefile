# Makefile for easy development workflows.
# See docs/development.md for docs.
# Note GitHub Actions call uv directly, not this Makefile.

.PHONY: help install dev-setup upgrade test lint format check typecheck security clean build pre-commit

.DEFAULT_GOAL := help

help:
	@echo "Available commands:"
	@echo "  install        - Install dependencies"
	@echo "  dev-setup      - Complete development setup"
	@echo "  upgrade        - Upgrade dependencies"
	@echo "  test           - Run tests"
	@echo "  lint           - Run linter (ruff check + codespell + bandit)"
	@echo "  format         - Run formatter (ruff format)"
	@echo "  typecheck      - Run type checker (ty)"
	@echo "  security       - Run security scanner (bandit)"
	@echo "  check          - Run all quality checks"
	@echo "  pre-commit     - Run pre-commit hooks on all files"
	@echo "  clean          - Clean build artifacts"
	@echo "  build          - Build package"

install:
	uv sync

dev-setup: install
	uv sync --all-extras --dev
	uv pip install -e .
	@echo "Development environment ready!"

upgrade:
	uv sync --upgrade

test:
	uv run pytest

lint:
	uv run devtools/lint.py

format:
	uv run ruff format src/ tests/ devtools/

typecheck:
	uv run ty check src/

# Check-only lint, matching CI (does not modify files).
lint-check:
	uv run python devtools/lint.py --check
pre-commit:
	uv run pre-commit run --all-files
# Clean build artifacts
clean:
	-rm -rf dist/
	-rm -rf *.egg-info/
	-rm -rf .pytest_cache/
	-rm -rf .ruff_cache/
	-rm -rf .mypy_cache/
	-rm -rf .venv/
	-find . -type d -name "__pycache__" -exec rm -rf {} +

build: clean
	uv build
