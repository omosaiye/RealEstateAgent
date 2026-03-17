# Real Estate Listing Monitor Agent

This repository contains the bootstrap scaffold for the Real Estate Listing Monitor Agent MVP described in [PRD.md](/Users/dadsomosaiye/devProjects/RealEstateAgent/PRD.md).

Milestone 1 through Milestone 5 are now in place, and the Milestone 6 Telegram service module is implemented. The project includes the bootstrap structure, YAML config loading, normalized models, provider normalization, deterministic listing filtering, SQLite-backed state and deduplication helpers, and plain-text Telegram alert formatting and delivery helpers.

## Current Status

- Project bootstrap is complete.
- Config loading and core data models are implemented.
- Provider fetching and normalization are implemented.
- Filtering is implemented with unit test coverage.
- SQLite state and deterministic deduplication are implemented with unit test coverage.
- Deterministic Telegram formatting, message splitting, and Bot API delivery are implemented in the service layer.
- Main orchestration and LLM summarization are not implemented yet.

## Project Structure

- `config/`: search configuration files
- `src/`: application code
- `tests/`: test suite placeholders
- `scripts/`: helper scripts
- `.github/workflows/`: future GitHub Actions workflow

## Local Setup

1. Create a virtual environment:
   `python3.11 -m venv .venv`
2. Activate it:
   `source .venv/bin/activate`
3. Install dependencies:
   `pip install -r requirements.txt`

## Checks

- Lint: `ruff check .`
- Tests: `pytest`

## Database Bootstrap

- Create the local SQLite state database with `python scripts/bootstrap_db.py`.
- Use `python scripts/bootstrap_db.py --db-path /tmp/listing_state.db` to target a custom path.

## Notes

- Secrets belong in environment variables. Use `.env.example` as a reference.
- `config/searches.yaml` includes one sample search that matches the PRD-required fields.
