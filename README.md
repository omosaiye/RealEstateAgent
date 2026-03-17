# Real Estate Listing Monitor Agent

This repository contains the Real Estate Listing Monitor Agent MVP described in [PRD.md](/Users/dadsomosaiye/devProjects/RealEstateAgent/PRD.md).

Milestone 1 through Milestone 8 are now in place. The project includes the bootstrap structure, YAML config loading, normalized models, provider normalization, deterministic listing filtering, SQLite-backed state and deduplication helpers, plain-text Telegram alert formatting and delivery helpers, an LLM summarizer service with deterministic fallback output, and local main orchestration.

## Current Status

- Project bootstrap is complete.
- Config loading and core data models are implemented.
- Provider fetching and normalization are implemented.
- Filtering is implemented with unit test coverage.
- SQLite state and deterministic deduplication are implemented with unit test coverage.
- Deterministic Telegram formatting, message splitting, and Bot API delivery are implemented in the service layer.
- LLM summarization is implemented in the service layer with a prompt template, OpenAI-backed request path, and deterministic fallback formatter.
- Main orchestration is implemented in `src/main.py`.

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

## Local Run

- Run once with `python -m src.main`
- You can also run `python src/main.py`
- Pass overrides such as `python -m src.main --config-path config/searches.yaml --db-path listing_state.db --log-level INFO`
- If your virtual environment is not activated, use `.venv/bin/python -m src.main`

## Checks

- Lint: `ruff check .`
- Tests: `pytest`

## Database Bootstrap

- Create the local SQLite state database with `python scripts/bootstrap_db.py`.
- Use `python scripts/bootstrap_db.py --db-path /tmp/listing_state.db` to target a custom path.
- Run the local orchestration helper with `./scripts/run_local.sh`

## Notes

- Secrets belong in environment variables. Use `.env.example` as a reference.
- `config/searches.yaml` includes one sample search that matches the PRD-required fields.
- `OPENAI_API_KEY` is required when instantiating the OpenAI summarizer service.
- `LISTING_PROVIDER_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID` are required for the default end-to-end local run path.
