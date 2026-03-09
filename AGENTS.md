# AGENTS.md

This file provides guidance for AI coding agents working in this repository.

## Project Overview

**Ladning** is a Python application that automatically schedules Tesla charging via an Easee EV charger, optimizing for cheap electricity prices sourced from [Strømligning](https://stromligning.dk).

## Repository Structure

```
ladning/          # Core application package
  charging_plan.py  # Charging plan calculation and scheduling logic
  constants.py      # Vehicle/charger constants (battery capacity, charging rates, etc.)
  energy_prices.py  # Fetches hourly electricity prices from Strømligning
  logging.py        # Logging setup
  types.py          # Shared dataclasses (Price, ChargingPlan, ChargingRequest, etc.)
  vehicle_query.py  # Queries Tesla vehicle charge state via TeslaPy
  webservice.py     # Flask-based REST API for querying and controlling charging
main.py           # Application entry point; connects Easee, Tesla, webservice, and scheduler
test/             # pytest test suite
```

## Environment Setup

This project uses [`uv`](https://docs.astral.sh/uv/) for dependency management and requires Python ≥ 3.13.

```bash
# Install uv first (see https://docs.astral.sh/uv/getting-started/installation/)
uv sync
```

## Common Commands

| Task | Command |
|------|---------|
| Run tests | `uv run pytest` |
| Lint | `uv run ruff check` |
| Run the application | `uv run main.py --easee_username <u> --easee_password <p> --tesla_username <u>` |

The CI pipeline (`.github/workflows/python-app.yml`) runs both `pytest` and `ruff check` on every push/PR to `develop`.

## Coding Conventions

- **Python 3.13+** — use modern type hints (`list[str]` instead of `List[str]` for new code, though the existing codebase uses `typing` imports).
- **Dataclasses** for value objects (see `ladning/types.py`).
- **No inline comments** unless necessary to explain non-obvious logic; prefer docstrings on functions.
- **Linting**: `ruff` is the linter/formatter. Ensure `uv run ruff check` passes before submitting changes.
- **Async**: The application is `asyncio`-based. Keep I/O-bound operations async; the webservice runs on a separate thread and communicates back via `asyncio.run_coroutine_threadsafe`.

## Testing

Tests live in `test/` and use `pytest`. Run them with:

```bash
uv run pytest
```

When adding new features, add corresponding tests in the `test/` directory following the existing patterns (see `test/test_charging_plan.py` for examples of unit tests with time-based scenarios).
