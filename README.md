# Real Estate Listing Monitor Agent

This repository contains the MVP for the Real Estate Listing Monitor Agent described in `PRD.md`.

The application is a scheduled Python workflow that:

1. fetches listings from a provider adapter
2. filters listings against YAML search criteria
3. deduplicates new versus previously seen listings
4. summarizes matched listings with OpenAI, with deterministic fallback text if the API request fails
5. sends alerts to Telegram
6. stores listing state in SQLite

This README is written for a junior engineer setting up the project from scratch.

## Current Implementation Status

- Local orchestration is implemented in `src/main.py`.
- Search config loading is implemented in `src/config.py`.
- Deterministic filtering, deduplication, SQLite state handling, Telegram delivery, and summarization are implemented and covered by tests.
- A GitHub Actions workflow exists at `.github/workflows/listing_monitor.yml`.
- The checked-in provider is still a sample adapter in `src/providers/sample_provider.py`.

Important current limitations:

- The sample provider points to `https://api.example.com/v1/listings`, which is a placeholder endpoint. A default end-to-end run will not succeed against real listing data until the provider adapter is wired to a real API.
- The GitHub Actions workflow uses a fresh runner each time, so the default SQLite file does not persist between workflow runs.

## Repository Layout

```text
.
├── config/
│   └── searches.yaml
├── scripts/
│   ├── bootstrap_db.py
│   └── run_local.sh
├── src/
│   ├── config.py
│   ├── logging_setup.py
│   ├── main.py
│   ├── models.py
│   ├── prompts/
│   ├── providers/
│   └── services/
├── tests/
├── .env.example
├── PRD.md
├── README.md
└── requirements.txt
```

## Prerequisites

Install these before you start:

- Python 3.11
- `pip`
- Git

You will also need these secrets for a real run:

- `LISTING_PROVIDER_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `OPENAI_API_KEY`

## Environment Setup

Create and activate a virtual environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

Install project dependencies:

```bash
pip install -r requirements.txt
```

Optional quick import check:

```bash
python -c "import httpx, yaml"
```

## Configure Environment Variables

Copy the example file:

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```dotenv
LISTING_PROVIDER_API_KEY=your-provider-api-key
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-telegram-chat-id
OPENAI_API_KEY=your-openai-api-key
LISTING_MONITOR_DRY_RUN=0
```

Load those values into your current shell session:

```bash
set -a
source .env
set +a
```

Important notes:

- The application does not automatically load `.env` files. If you skip the `source .env` step, the app will not see your secrets.
- `src.main` creates `SampleListingProvider()`, `OpenAISummarizer()`, and `TelegramNotifier()` during startup. That means all four environment variables above are required for the default app entrypoint.
- If dry-run mode is enabled, `src.main` skips real Telegram setup and delivery. In that mode, `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are not required for the default entrypoint.
- If `OPENAI_API_KEY` is missing, startup fails before the summarizer fallback logic is reached. The fallback only helps after the OpenAI request is attempted and fails.

## Configure `config/searches.yaml`

Searches are loaded from `config/searches.yaml`.

Current sample file:

```yaml
searches:
  - search_name: raleigh_primary
    enabled: true
    location: "Raleigh, NC"
    max_price: 550000
    min_beds: 3
    min_baths: 2
    property_types:
      - single_family
      - townhome
    max_hoa: 250
    min_sqft: 1600
    keywords_include:
      - garage
    keywords_exclude:
      - leasehold
      - auction
```

Field reference:

- `search_name`: Stable identifier used in logs and the SQLite state table.
- `enabled`: `true` runs the search, `false` skips it.
- `location`: Location string sent to the provider adapter.
- `max_price`: Maximum allowed listing price in whole dollars.
- `min_beds`: Minimum bedroom count.
- `min_baths`: Minimum bathroom count.
- `property_types`: Allowed property types. This must be a non-empty list.
- `max_hoa`: Optional maximum monthly HOA fee.
- `min_sqft`: Optional minimum square footage.
- `keywords_include`: Optional list of words or phrases that should appear in the listing text.
- `keywords_exclude`: Optional list of words or phrases that should not appear in the listing text.

Validation rules enforced by the app:

- `searches` must exist as a top-level YAML list.
- Required fields must be present for each search.
- `enabled` must be `true` or `false`.
- `max_price` must be an integer.
- `min_beds` and `min_baths` may be integers or decimals.
- List fields must contain only non-empty strings.

## Bootstrap the SQLite Database

You can create the SQLite state database explicitly:

```bash
python scripts/bootstrap_db.py
```

Use a custom location if needed:

```bash
python scripts/bootstrap_db.py --db-path /tmp/listing_state.db
```

Notes:

- The default database path is `listing_state.db` in the repository root.
- `src.main` also bootstraps the database automatically on startup, so this step is optional for normal local runs.

## Run the App Locally

Run the application once with default paths:

```bash
python -m src.main
```

Equivalent direct script form:

```bash
python src/main.py
```

Run with explicit options:

```bash
python -m src.main \
  --config-path config/searches.yaml \
  --db-path listing_state.db \
  --log-level INFO
```

Run a safe end-to-end dry run:

```bash
python -m src.main --dry-run
```

You can also enable dry run from the environment:

```bash
LISTING_MONITOR_DRY_RUN=1 python -m src.main
```

Use the helper script if you want the repo to always run with `.venv/bin/python`:

```bash
./scripts/run_local.sh
```

Pass flags through the helper script the same way:

```bash
./scripts/run_local.sh --log-level DEBUG --db-path /tmp/listing_state.db
```

What a normal run does:

1. loads search definitions from `config/searches.yaml`
2. creates the SQLite state table if it does not exist
3. fetches listings for each enabled search
4. filters and classifies listings
5. summarizes sendable listings
6. sends Telegram messages
7. updates SQLite state after successful sends

What dry-run mode does:

- still loads config, bootstraps the database, fetches listings, filters them, deduplicates them, and builds the summary
- skips Telegram delivery
- logs the exact message that would have been sent
- skips listing state updates so test runs do not mark listings as sent

Important safety note:

- `python -m src.main --dry-run` is the safe local test path for Milestone 10.1.
- A real `python -m src.main` run without `--dry-run` will attempt to send a Telegram message if the provider returns new or changed listings.

Important current limitation:

- The checked-in `SampleListingProvider` uses a placeholder base URL. Until the provider adapter is connected to a real listing API, the default end-to-end local run is mainly useful for startup checks, failure-path testing, and understanding the orchestration flow.

## Run Tests and Checks

Run the full test suite:

```bash
pytest
```

Run a single test module:

```bash
pytest tests/test_main.py
```

Run lint checks:

```bash
ruff check .
```

These tests mock external calls. You do not need live provider, Telegram, or OpenAI access to run them.

## Dry-Run Mode

Milestone 10.1 is implemented.

Enable it with either:

- `python -m src.main --dry-run`
- `LISTING_MONITOR_DRY_RUN=1 python -m src.main`

Dry-run behavior:

- the app logs the message that would have been sent to Telegram
- the app does not call the Telegram Bot API
- the app does not update listing state after the run
- the rest of the pipeline still runs so you can verify end-to-end behavior safely

## GitHub Actions Deployment

The workflow file is:

```text
.github/workflows/listing_monitor.yml
```

Current workflow behavior:

- runs on a schedule every 6 hours
- supports manual runs with `workflow_dispatch`
- installs dependencies with `pip`
- runs `python -m src.main --log-level INFO`

### Required GitHub Repository Secrets

Add these repository secrets before running the workflow:

- `LISTING_PROVIDER_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `OPENAI_API_KEY`

### Manual Deployment Smoke Test

To run the workflow manually:

1. Push your branch to GitHub.
2. Open the repository on GitHub.
3. Go to the `Actions` tab.
4. Select the `Listing Monitor` workflow.
5. Click `Run workflow`.
6. Choose the branch.
7. Click `Run workflow` again.
8. Open the job logs and confirm the Python run completed.

### Important Deployment Notes

- The current workflow does not persist `listing_state.db` between runs because GitHub-hosted runners are ephemeral.
- That means deduplication state is not preserved across scheduled workflow runs yet.
- The current workflow still depends on the sample provider adapter, so a real production deployment is blocked until a real provider endpoint is implemented.
- Manual `workflow_dispatch` runs are not dry runs unless you explicitly pass or configure dry-run behavior for the workflow command.

## Troubleshooting

### `python3.11: command not found`

Python 3.11 is not installed or is not on your shell path. Install Python 3.11, then retry:

```bash
python3.11 --version
```

### `Expected virtualenv Python at .../.venv/bin/python`

You ran `./scripts/run_local.sh` before creating the virtual environment. Fix it with:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### `LISTING_PROVIDER_API_KEY environment variable is required`

Your shell does not have the provider API key loaded. Re-source `.env`:

```bash
set -a
source .env
set +a
```

The same fix applies to missing `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, or `OPENAI_API_KEY`.

### The app still says a variable is missing even though `.env` exists

The code does not auto-read `.env`. The file must be sourced into the shell you are using to run Python.

Verify one variable:

```bash
echo "$OPENAI_API_KEY"
```

If it prints nothing, the variable is not loaded into your shell session.

### `Search config file not found` or YAML validation errors

Check that the file exists and is valid YAML:

```bash
ls config/searches.yaml
python -c "from src.config import load_searches; print(load_searches())"
```

Common causes:

- wrong file path passed to `--config-path`
- bad indentation in YAML
- missing required fields
- empty strings inside list fields

### The app fails during provider fetch

This is expected with the checked-in sample provider unless you replace the placeholder endpoint with a real provider implementation.

Current default provider URL:

```text
https://api.example.com/v1/listings
```

### The app fails when sending Telegram messages

Check that:

- `TELEGRAM_BOT_TOKEN` is correct
- `TELEGRAM_CHAT_ID` is correct
- your bot has permission to message that chat
- your network can reach `https://api.telegram.org`

Run tests first if you want to verify the service layer without sending live messages:

```bash
pytest tests/test_telegram_service.py
```

### GitHub Actions runs but does not remember prior listings

This is the current behavior of the checked-in workflow. Each GitHub-hosted runner starts with a clean filesystem, so the default SQLite database is recreated on each run.

## Suggested Local Verification Order

If you are new to the project, follow this order:

1. Create and activate `.venv`.
2. Install dependencies.
3. Copy `.env.example` to `.env`.
4. Fill in secrets and source `.env`.
5. Review `config/searches.yaml`.
6. Run `pytest`.
7. Run `ruff check .`.
8. Run `python scripts/bootstrap_db.py`.
9. Run `python -m src.main` only after you understand the current provider and Telegram limitations described above.
