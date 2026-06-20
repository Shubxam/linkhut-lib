# Development Guide

This document outlines the development setup and tools for the linkhut-lib project.

## Setup

1. **Install dependencies:**
   ```bash
   uv sync --all-extras --dev
   ```

## Development Tools

All linting, formatting, type checking, security scanning, and spell checking
are orchestrated through the project's `Makefile` and the
`devtools/lint.py` script.

### Quick reference

| Command            | What it does                                                |
| ------------------ | ----------------------------------------------------------- |
| `make install`     | `uv sync` — install runtime deps                           |
| `make dev-setup`   | `uv sync --all-extras --dev` + editable install            |
| `make lint`        | Run ruff (check + format), codespell, ty, bandit (auto-fix) |
| `make lint-check`  | Same as `make lint` but in CI check-only mode (no edits)   |
| `make format`      | `ruff format`                                               |
| `make typecheck`   | `ty check src/`                                             |
| `make security`    | `bandit` security scan                                       |
| `make test`        | `pytest`                                                    |
| `make build`       | `uv build` (wheel + sdist)                                  |
| `make clean`       | Remove build artifacts, caches, `.venv/`                    |

### Manual commands

If you need to run a single tool directly:

```bash
uv run ruff check src/          # Linting
uv run ruff format src/         # Formatting
uv run ty check                 # Type checking
uv run bandit -r src/           # Security scanning
uv run codespell src/ docs/     # Spell checking

uv run pytest                   # Tests
```

### Type Checking

This project uses `ty` (Astral's type checker) in strict mode:

```bash
uv run ty check
```

`ty` is still in alpha; expect occasional false positives.

### Configuration

- **Ruff / codespell / bandit / ty / pytest:** all configured in `pyproject.toml`.
- **CI:** `.github/workflows/ci.yml` runs `make lint-check` and `make test`
  on every push and pull request, across the Python versions listed in the
  `pyproject.toml` `requires-python` field.

## Workflow

1. Make your changes.
2. Run `make lint` to auto-format and fix what can be fixed.
3. Run `make lint-check` to confirm CI parity.
4. Run `make test` and `make typecheck`.
5. Commit and push — CI will run the same checks.

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull
request to `main`. The supply-chain cool-off (`UV_EXCLUDE_NEWER=14 days`)
means CI will refuse to resolve packages that have been on PyPI for less
than two weeks.
