# Makefile for linkhut-lib

.PHONY: help install test lint format check clean build

.DEFAULT_GOAL := help

# Display help
help:
	@echo "Available commands:"
	@echo "  install     - Install dependencies"
	@echo "  test        - Run tests"
	@echo "  lint        - Run linter"
	@echo "  format      - Format code"
	@echo "  check       - Run all checks (lint + type + format)"
	@echo "  clean       - Clean build artifacts"
	@echo "  build       - Build package"
	@echo "  dev-setup   - Complete development setup"

# Install dependencies
install:
	uv sync --group dev

# Run tests
test:
	uv run pytest

# Run linter
lint:
	uv run ruff check src/

# Format code
format:
	uv run ruff format src/

# Run all quality checks
check:
	uv run ruff check src/
	uv run ruff format src/ --check
	uv run ty check
	uv run bandit -r src/

# Clean build artifacts
clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .ruff_cache/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

# Build package
build: clean
	uv build

# Development setup
dev-setup: install
	uv run pre-commit install
	@echo "Development environment ready!"
