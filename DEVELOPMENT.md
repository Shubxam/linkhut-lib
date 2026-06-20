# Development Guide

This document outlines the development setup and tools for the linkhut-lib project.

## Setup

1. **Install dependencies:**
   ```bash
   uv sync --group dev
   ```

2. **Install pre-commit hooks:**
   ```bash
   uv run pre-commit install
   ```

## Development Tools

### Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality. The hooks run automatically on every commit and include:

- **Code Quality & Formatting:**
  - `ruff` - Fast Python linter and formatter
  - `pyupgrade` - Upgrades Python syntax to modern versions
  
- **Security:**
  - `bandit` - Security linter for Python code
  
- **Spell Checking:**
  - `codespell` - Catches common spelling mistakes
  
- **File Quality:**
  - Trailing whitespace removal
  - End-of-file fixing
  - YAML/TOML validation
  - Merge conflict detection

### Manual Commands

You can also run these tools manually:

```bash
# Run all pre-commit hooks on all files
uv run pre-commit run --all-files

# Run specific tools
uv run ruff check src/          # Linting
uv run ruff format src/         # Formatting
uv run ty check                 # Type checking
uv run bandit -r src/           # Security scanning
uv run codespell src/           # Spell checking

# Run tests
uv run pytest

# Update pre-commit hooks
uv run pre-commit autoupdate
```

### Type Checking

This project uses `ty` (Astral's type checker) for type checking:

```bash
uv run ty check
```

Note: `ty` is not included in pre-commit hooks yet as it's still in alpha, but it's available as a dev dependency.

### Configuration

- **Ruff:** Configured in `pyproject.toml` under `[tool.ruff]`
- **Bandit:** Configured in `pyproject.toml` under `[tool.bandit]`
- **Pre-commit:** Configured in `.pre-commit-config.yaml`
- **Pytest:** Configured in `pyproject.toml` under `[tool.pytest.ini_options]`

## Workflow

1. Make your changes
2. Run tests: `uv run pytest`
3. Run type checking: `uv run ty check`
4. Commit your changes (pre-commit hooks will run automatically)
5. If hooks fail, fix the issues and commit again

## CI/CD

The `.pre-commit-config.yaml` includes configuration for [pre-commit.ci](https://pre-commit.ci), which will:
- Run hooks on pull requests
- Auto-fix issues when possible
- Keep hooks updated weekly