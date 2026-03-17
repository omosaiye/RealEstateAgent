# AGENTS.md

## Purpose

This repository contains the **Real Estate Listing Monitor Agent**.

The system is a scheduled Python workflow that:
1. fetches real estate listings from a provider API,
2. filters listings using configured search criteria,
3. deduplicates new vs. previously seen listings,
4. optionally summarizes matched listings with an LLM,
5. sends alerts to Telegram,
6. stores state so unchanged listings are not repeatedly sent.

Read `PRD.md` before making major changes.

---

## Working Style

Follow these rules when making changes:

- Keep changes **small, focused, and easy to review**.
- Prefer simple code over clever code.
- Prefer functions that do **one thing well**.
- Do not introduce heavy frameworks unless explicitly required by `PRD.md`.
- Do not add a web frontend, queue, container orchestration, or background worker unless explicitly requested.
- Do not over-engineer abstractions. Use only the interfaces already planned in `PRD.md`.
- When a task can be broken into smaller steps, do the smallest useful step first.
- Update documentation when behavior or setup changes.

---

## Primary Goal

Build the MVP described in `PRD.md` using this priority order:

1. local deterministic pipeline,
2. tests,
3. Telegram delivery,
4. LLM summarization,
5. scheduled deployment.

Do **not** start with deployment.
Do **not** start with the LLM.
Do **not** start with browser automation.

---

## Scope Guardrails

### In Scope
- Python 3.11
- scheduled job design
- single Telegram destination
- listing provider adapter
- YAML-based search configuration
- SQLite state storage
- LLM summarization with fallback
- GitHub Actions scheduler
- unit tests and simple local run support

### Out of Scope for MVP
- Zillow scraping
- WhatsApp delivery
- web UI
- multi-user support
- long-running daemon processes
- browser automation
- complex ranking engines
- vector databases
- agent frameworks
- full orchestration platforms

If asked to add out-of-scope features, isolate the change and avoid breaking MVP simplicity.

---

## Repository Expectations

Expected structure:

```text
repo-root/
  AGENTS.md
  PRD.md
  README.md
  requirements.txt
  .env.example
  config/
    searches.yaml
  src/
    main.py
    config.py
    models.py
    logging_setup.py
    providers/
      __init__.py
      base.py
      sample_provider.py
    services/
      filter_service.py
      dedupe_service.py
      summarize_service.py
      telegram_service.py
      state_service.py
    prompts/
      listing_summary.txt
  tests/
    test_filter_service.py
    test_dedupe_service.py
    test_provider_adapter.py
    test_telegram_service.py
  scripts/
    bootstrap_db.py
    run_local.sh
  .github/
    workflows/
      listing_monitor.yml
```

If files are missing, create them only when needed for the current task.

---

## Engineering Principles

### 1. Keep business logic deterministic
Filtering, deduplication, and scheduling must be deterministic.

### 2. Use the LLM only for summarization
Do not use the LLM for:
- retry logic,
- filtering logic,
- deduplication decisions,
- state management,
- orchestration control flow.

### 3. Keep network code isolated
External calls should live in clearly named service/provider modules.

### 4. Make failures understandable
Errors should be logged with enough context for a junior engineer to debug them.

### 5. Preserve replaceability
Keep provider, summarizer, and notifier logic behind simple interfaces.

---

## Required Interfaces

Keep or implement these interfaces unless explicitly told otherwise.

### Listing provider interface
```python
class ListingProvider:
    def fetch_listings(self, search_config) -> list:
        raise NotImplementedError
```

### Summarizer interface
```python
class ListingSummarizer:
    def summarize(self, search_name: str, listings: list) -> str:
        raise NotImplementedError
```

### Notifier interface
```python
class Notifier:
    def send_message(self, message: str) -> None:
        raise NotImplementedError
```

Do not add unnecessary layers above these interfaces.

---

## Coding Standards

- Use Python type hints on public functions.
- Use dataclasses or simple models where appropriate.
- Keep functions short and readable.
- Add docstrings for public modules, classes, and non-obvious functions.
- Avoid giant files.
- Avoid hidden side effects.
- Avoid global mutable state when possible.
- Use explicit timeouts on all HTTP calls.
- Use environment variables for secrets.
- Never hardcode tokens, chat IDs, or API keys.
- Never log secrets.

---

## Configuration Rules

Search configuration must come from `config/searches.yaml`.

Required search fields should match `PRD.md`.

Secrets must come from environment variables, including:

- `LISTING_PROVIDER_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `OPENAI_API_KEY`

If a secret is missing, fail clearly with a readable error message.

---

## State Management Rules

Use SQLite as the default state store for MVP.

State must support:
- detecting new listings,
- detecting price changes,
- detecting status changes,
- avoiding duplicate alerts.

Do not replace SQLite with a hosted database unless explicitly requested.

---

## Testing Rules

Write or update tests whenever behavior changes.

Minimum testing expectations:
- provider normalization tests,
- filtering tests,
- deduplication tests,
- Telegram service tests,
- summarizer fallback tests when summarizer is implemented.

Testing rules:
- mock all external API calls,
- do not require live provider or Telegram access for unit tests,
- keep tests readable and focused,
- prefer small test fixtures.

---

## Logging Rules

Include logs for:
- run start,
- search start,
- provider fetch completion,
- filter completion,
- dedupe completion,
- summary completion,
- Telegram send completion,
- run completion,
- run failure.

Logs should help answer:
- what search ran,
- how many listings were fetched,
- how many matched,
- how many were sent,
- where a failure occurred.

---

## Deployment Rules

Deployment target for MVP is GitHub Actions scheduled workflow.

Before adding the workflow:
1. make the app run locally,
2. make tests pass,
3. make dry-run mode work.

Do not add unnecessary CI complexity.

---

## Safe Change Process

For each task:

1. Read the relevant section in `PRD.md`.
2. Identify the smallest complete slice of work.
3. Implement that slice.
4. Add or update tests.
5. Run relevant checks.
6. Update `README.md` if setup or behavior changed.

If a requested change is large, split it into smaller commits or patches internally.

---

## Task Ordering

Use this implementation order unless told otherwise:

1. Bootstrap repo
2. Config and models
3. Provider adapter
4. Filtering
5. SQLite state
6. Deduplication
7. Telegram deterministic formatter
8. Main orchestration
9. LLM summarization
10. GitHub Actions
11. QA hardening

---

## Definition of Good Output

A good implementation:
- is understandable by a junior engineer,
- matches `PRD.md`,
- includes tests,
- avoids scope creep,
- is easy to run locally,
- does not depend on manual production-only steps to verify.

---

## When Unsure

If requirements are ambiguous:
- prefer the simpler implementation,
- follow `PRD.md`,
- avoid adding speculative features,
- keep the code modular enough for later changes,
- leave concise TODO comments only when truly necessary.

---

## Immediate Next Step

If starting from scratch:
1. create the base repo structure,
2. add `requirements.txt`,
3. add `.env.example`,
4. add sample `config/searches.yaml`,
5. implement config loading and models first.

If continuing from existing code:
- inspect current files,
- compare against `PRD.md`,
- complete the next unfinished milestone in order.
