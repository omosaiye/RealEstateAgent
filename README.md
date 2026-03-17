# Real Estate Listing Monitor Agent

This repository contains the bootstrap scaffold for the Real Estate Listing Monitor Agent MVP described in [PRD.md](/Users/dadsomosaiye/devProjects/RealEstateAgent/PRD.md).

Only Milestone 1 is set up right now. The project structure, dependency list, environment template, and placeholder files are in place so future milestones can build on a clear foundation.

## Current Status

- Project bootstrap is complete.
- Application logic is not implemented yet.
- Placeholder files mark the planned modules from the PRD.

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
- `config/searches.yaml` is a placeholder and will be filled in during a later milestone.
