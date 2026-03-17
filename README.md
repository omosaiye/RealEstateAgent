# Real Estate Listing Monitor Agent

This repository contains the bootstrap scaffold for the Real Estate Listing Monitor Agent MVP described in [PRD.md](/Users/dadsomosaiye/devProjects/RealEstateAgent/PRD.md).

Milestone 1 and Milestone 2 are now in place. The project includes the bootstrap structure plus a simple YAML config loader, search configuration models, and the normalized listing model.

## Current Status

- Project bootstrap is complete.
- Config loading and core data models are implemented.
- Provider fetching, filtering, deduplication, Telegram delivery, and LLM summarization are not implemented yet.

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

## Notes

- Secrets belong in environment variables. Use `.env.example` as a reference.
- `config/searches.yaml` now includes one sample search that matches the PRD-required fields.
