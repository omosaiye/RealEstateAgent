# PRD: Real Estate Listing Monitor Agent

## 1. Document Control

- **Project Name:** Real Estate Listing Monitor Agent
- **Version:** 1.0
- **Audience:** Junior software engineers with ~1 year of experience
- **Primary Goal:** Build a scheduled system that searches real estate listings in a target area, filters and deduplicates them, summarizes the results with an LLM, and sends the summary to a Telegram chat.
- **Target Release:** MVP in 2 weeks of part-time work or 1 week of focused work

---

## 2. Product Summary

We are building a lightweight “autonomous agent” for real estate monitoring.

This is **not** a browser robot and **not** a continuously running AI agent.

Instead, it is a scheduled workflow that:
1. Runs on a schedule
2. Calls a real estate listings provider API
3. Filters listings based on user preferences
4. Detects new listings and price changes
5. Calls an LLM to create a short summary
6. Sends the results to a Telegram chat
7. Saves state so the same listing is not sent repeatedly

The system must be simple, reliable, inexpensive, and easy to debug.

---

## 3. Goals

### 3.1 Business Goals
- Notify the user of relevant new listings automatically
- Reduce manual searching effort
- Provide readable summaries instead of raw data
- Make it easy to change search criteria later

### 3.2 User Goals
The user wants:
- Alerts for listings in a specific area
- Alerts only for matching listings
- No repeated spam for the same listing
- Clear summaries delivered in Telegram
- An easy path to add more search areas later

### 3.3 Engineering Goals
- Clean, modular code
- Easy local testing
- Easy deployment using GitHub Actions
- Minimal infrastructure
- Clear logs and failure handling

---

## 4. Non-Goals

The MVP will **not** include:
- Zillow browser scraping
- WhatsApp delivery
- Always-on background processes
- Multiple users or accounts
- Web UI or dashboard
- Complex ranking models
- Interactive chat with the agent
- Image processing for listings
- Map-based polygon search UI
- Buying/renting decision support beyond simple summaries

---

## 5. Users and Use Cases

## 5.1 Primary User
One technical user who wants listing alerts in Telegram.

## 5.2 Core Use Cases
1. User defines search criteria such as city, ZIP code, max price, minimum beds, and property type.
2. System checks the listing source every N hours.
3. System sends only new or changed listings.
4. User receives a Telegram message with a short, useful summary.
5. User can later update criteria in a config file.

---

## 6. MVP Scope

### 6.1 Included
- Scheduled execution
- Single Telegram destination
- Single listing provider adapter
- Search criteria from config file
- Deduplication by listing ID
- Price-change detection
- LLM summary generation
- Logs
- Basic unit tests
- GitHub Actions deployment

### 6.2 Excluded
- Database server
- Frontend
- Multi-channel messaging
- Browser automation
- Account login to listing websites
- Human approval workflow

---

## 7. Success Metrics

### 7.1 Functional Metrics
- System successfully runs on schedule
- System retrieves listings from provider API
- System filters listings correctly
- System sends Telegram messages successfully
- System does not resend unchanged listings

### 7.2 Quality Metrics
- 90%+ of runs complete without manual intervention
- Duplicate alerts are rare
- Error logs are readable
- Junior engineer can run locally in under 30 minutes

---

## 8. High-Level Architecture

```text
Scheduler (GitHub Actions)
    -> main.py
        -> listings provider adapter
        -> filtering engine
        -> dedupe/state store
        -> LLM summarizer
        -> Telegram notifier
        -> logging
        -> local state persistence
```

### 8.1 Architecture Principles
- Keep the workflow deterministic
- Use the LLM only for summarization, not control logic
- Store minimal state locally in JSON or SQLite
- Design the listings provider as an adapter so it can be swapped later

---

## 9. Technical Stack

- **Language:** Python 3.11
- **Scheduler:** GitHub Actions
- **Messaging:** Telegram Bot API
- **Storage:** SQLite for production-like simplicity, JSON allowed for earliest bootstrap
- **LLM Access:** OpenAI API or pluggable provider
- **HTTP Client:** `httpx`
- **Config Management:** environment variables + `config/searches.yaml`
- **Testing:** `pytest`
- **Linting/Formatting:** `ruff`
- **Package Management:** `uv` or `pip`

### 9.1 Why SQLite
SQLite is simple, local, and good enough for one-user scheduled jobs.

### 9.2 Why Adapter Pattern
Different listing providers return different fields. The adapter isolates provider-specific logic.

---

## 10. Repository Structure

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

---

## 11. Functional Requirements

## 11.1 Search Configuration
The system must load search criteria from a YAML file.

Minimum supported fields:
- `search_name`
- `location`
- `max_price`
- `min_beds`
- `min_baths`
- `property_types`
- `max_hoa` (optional)
- `min_sqft` (optional)
- `keywords_include` (optional)
- `keywords_exclude` (optional)
- `enabled`

Example:

```yaml
searches:
  - search_name: raleigh_primary
    enabled: true
    location: "Raleigh, NC"
    max_price: 550000
    min_beds: 3
    min_baths: 2
    property_types: ["single_family", "townhome"]
    max_hoa: 250
    min_sqft: 1600
    keywords_include: ["garage"]
    keywords_exclude: ["leasehold", "auction"]
```

## 11.2 Provider Fetching
The system must:
- call the provider API
- normalize provider response into internal models
- handle empty results
- handle API failures gracefully

## 11.3 Filtering
The system must filter normalized listings using the configured criteria.

## 11.4 Deduplication
The system must detect:
- brand new listings
- existing listings with lower price
- existing listings with status change
- unchanged listings

## 11.5 Summarization
The system must call an LLM only for the listings that should be sent.

The summarizer must:
- produce a short digest
- explain why each listing matched
- keep output concise enough for Telegram

## 11.6 Telegram Delivery
The system must send:
- one summary message per search run
- optionally split long messages if needed
- include links to the listings

## 11.7 State Persistence
The system must persist, at minimum:
- listing ID
- last seen price
- last seen status
- last sent timestamp
- search name

## 11.8 Logging
The system must log:
- run start
- run end
- number of listings fetched
- number filtered
- number sent
- errors

---

## 12. Non-Functional Requirements

- Code must be understandable by junior engineers
- Each module should do one thing
- Most functions should be short and testable
- Network calls must have timeouts
- Failures in one search should not crash all searches
- Secrets must not be hardcoded
- Telegram token and provider API key must come from environment variables

---

## 13. Data Model

## 13.1 Internal Listing Model

```python
class Listing:
    listing_id: str
    search_name: str
    address: str
    city: str
    state: str
    zip_code: str | None
    price: int
    beds: float | None
    baths: float | None
    sqft: int | None
    property_type: str | None
    hoa_monthly: int | None
    status: str | None
    url: str
    description: str | None
    provider_name: str
    raw_payload: dict
```

## 13.2 State Table

Suggested SQLite table: `listing_state`

Columns:
- `listing_id` TEXT NOT NULL
- `search_name` TEXT NOT NULL
- `last_seen_price` INTEGER
- `last_seen_status` TEXT
- `last_sent_at` TEXT
- `first_seen_at` TEXT
- `updated_at` TEXT

Primary key:
- `(listing_id, search_name)`

---

## 14. External Interfaces

## 14.1 Listing Provider Interface

Create an abstract base class:

```python
class ListingProvider:
    def fetch_listings(self, search_config) -> list[Listing]:
        raise NotImplementedError
```

All providers must return normalized `Listing` objects.

## 14.2 LLM Interface

Create a summarizer interface:

```python
class ListingSummarizer:
    def summarize(self, search_name: str, listings: list[Listing]) -> str:
        raise NotImplementedError
```

## 14.3 Telegram Interface

Create a notifier interface:

```python
class Notifier:
    def send_message(self, message: str) -> None:
        raise NotImplementedError
```

---

## 15. Prompt Design for LLM

Prompt goals:
- summarize only the supplied listings
- do not invent missing data
- be concise
- explain why the listing matched the configured criteria
- format output for Telegram readability

Suggested prompt template:

```text
You are summarizing real estate listings for a Telegram alert.

Rules:
- Use only the provided listing data.
- Do not invent facts.
- Keep the message concise.
- For each listing, include address, price, beds/baths if present, and one sentence on why it matched.
- End with the direct listing URL.
- Use plain text suitable for Telegram.

Search name: {search_name}
User criteria: {criteria}
Listings:
{listing_json}
```

---

## 16. Telegram Message Format

Preferred format:

```text
🏠 Real Estate Monitor: {search_name}

Found {n} new or changed listings.

1) {address}
Price: ${price}
Beds/Baths: {beds}/{baths}
Why it matched: {short reason}
Link: {url}

2) ...
```

Rules:
- Maximize readability
- Keep each listing compact
- Avoid markdown features that may break in Telegram
- Split message if it exceeds Telegram length limits

---

## 17. Error Handling

### 17.1 Provider Errors
- log the error
- fail only the affected search
- continue with other searches if present

### 17.2 LLM Errors
- fall back to deterministic plain-text summary
- do not skip sending results if listings were found

### 17.3 Telegram Errors
- log the failure clearly
- return non-zero exit code so the scheduler marks the run as failed

### 17.4 State Write Errors
- fail the run
- log enough context for debugging

---

## 18. Security and Secrets

Secrets must live in environment variables:
- `LISTING_PROVIDER_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `OPENAI_API_KEY`

Rules:
- never commit `.env`
- include `.env.example`
- redact tokens in logs
- do not log full provider responses if they may contain unnecessary data

---

## 19. Observability

Minimum logging events:
- `run_started`
- `search_started`
- `provider_fetch_complete`
- `filter_complete`
- `dedupe_complete`
- `summary_complete`
- `telegram_send_complete`
- `run_complete`
- `run_failed`

Suggested log format:
- JSON logs or simple structured text with key fields

Example:
```text
event=filter_complete search_name=raleigh_primary fetched=45 matched=6 changed=3
```

---

## 20. Delivery Plan

Each task below must be small enough to complete in **half a day or less**.

## 20.1 Milestone 1: Project Bootstrap

### Task 1.1: Create repo structure
- Create folders and placeholder files from the repo structure section
- Add `README.md`
- Add `.gitignore`
- Add `.env.example`

**Estimate:** 2 hours

**Acceptance Criteria:**
- Repo structure exists
- Developer can clone and open project without confusion

### Task 1.2: Set up Python environment
- Add `requirements.txt`
- Install `httpx`, `pytest`, `ruff`, `pyyaml`
- Confirm imports work

**Estimate:** 2 hours

**Acceptance Criteria:**
- `pip install -r requirements.txt` succeeds
- `python -c "import httpx"` succeeds

### Task 1.3: Add lint and test commands
- Configure `ruff`
- Add basic `pytest` command
- Document commands in `README.md`

**Estimate:** 2 hours

**Acceptance Criteria:**
- `ruff check .` runs
- `pytest` runs with no fatal errors

---

## 20.2 Milestone 2: Config and Models

### Task 2.1: Implement config loader
- Create `src/config.py`
- Load YAML search config
- Validate required fields

**Estimate:** 3 hours

**Acceptance Criteria:**
- Valid YAML loads successfully
- Missing required fields raise readable errors

### Task 2.2: Implement listing model
- Create `src/models.py`
- Add `Listing` dataclass
- Add any helper types needed

**Estimate:** 2 hours

**Acceptance Criteria:**
- `Listing` can be instantiated in tests
- Field names are documented

### Task 2.3: Add sample config file
- Create `config/searches.yaml`
- Add one working example search

**Estimate:** 1 hour

**Acceptance Criteria:**
- App can start with the sample config

---

## 20.3 Milestone 3: Provider Adapter

### Task 3.1: Create provider base class
- Add `src/providers/base.py`
- Define the abstract provider interface

**Estimate:** 2 hours

**Acceptance Criteria:**
- Base class exists
- Method signatures are documented

### Task 3.2: Create sample provider adapter
- Add `src/providers/sample_provider.py`
- Implement API fetch logic
- Normalize response into `Listing` objects

**Estimate:** 4 hours

**Acceptance Criteria:**
- Provider returns a list of `Listing`
- Empty responses are handled
- Timeouts are set on network calls

### Task 3.3: Add provider unit test with mocked response
- Mock the provider API response
- Validate normalization

**Estimate:** 3 hours

**Acceptance Criteria:**
- Test verifies field mapping
- Test passes without live API access

---

## 20.4 Milestone 4: Filtering

### Task 4.1: Implement price, beds, baths filters
- Create `src/services/filter_service.py`
- Filter by core numeric fields

**Estimate:** 3 hours

**Acceptance Criteria:**
- Listings above max price are excluded
- Listings below minimum beds/baths are excluded

### Task 4.2: Implement optional filters
- Add property type, HOA, sqft, keyword include/exclude

**Estimate:** 4 hours

**Acceptance Criteria:**
- Optional fields work when present
- Missing optional listing fields do not crash the app

### Task 4.3: Add filter unit tests
- Cover happy path and edge cases

**Estimate:** 4 hours

**Acceptance Criteria:**
- Tests cover at least 8 scenarios

---

## 20.5 Milestone 5: State and Deduplication

### Task 5.1: Create SQLite bootstrap logic
- Add `scripts/bootstrap_db.py`
- Create `listing_state` table

**Estimate:** 3 hours

**Acceptance Criteria:**
- Running the script creates the database and table

### Task 5.2: Implement state service
- Add `src/services/state_service.py`
- Read and write listing state records

**Estimate:** 4 hours

**Acceptance Criteria:**
- Can upsert listing state
- Can fetch existing state by listing ID + search name

### Task 5.3: Implement dedupe service
- Add `src/services/dedupe_service.py`
- Detect new, changed, and unchanged listings

**Estimate:** 4 hours

**Acceptance Criteria:**
- New listings are marked sendable
- Price drops are marked sendable
- Unchanged listings are not sendable

### Task 5.4: Add dedupe unit tests
- Cover new listing, unchanged listing, price drop, status change

**Estimate:** 4 hours

**Acceptance Criteria:**
- All cases behave as expected

---

## 20.6 Milestone 6: Telegram Notifications

### Task 6.1: Implement Telegram client
- Add `src/services/telegram_service.py`
- Call Telegram sendMessage endpoint
- Add timeout and error handling

**Estimate:** 3 hours

**Acceptance Criteria:**
- Mocked send succeeds in tests
- Network errors raise readable exceptions

### Task 6.2: Implement message formatter
- Create deterministic formatter before LLM integration
- Support multiple listings in one message

**Estimate:** 3 hours

**Acceptance Criteria:**
- Formatter output is readable
- Empty list produces a sensible result

### Task 6.3: Add Telegram unit tests
- Mock outbound HTTP
- Verify payload content

**Estimate:** 3 hours

**Acceptance Criteria:**
- Tests assert correct endpoint and message payload

---

## 20.7 Milestone 7: LLM Summarization

### Task 7.1: Add prompt template file
- Create `src/prompts/listing_summary.txt`

**Estimate:** 1 hour

**Acceptance Criteria:**
- Prompt file exists and is readable from code

### Task 7.2: Implement summarizer service
- Add `src/services/summarize_service.py`
- Read prompt template
- Call LLM API
- Return summary text

**Estimate:** 4 hours

**Acceptance Criteria:**
- Service returns summary text for test input
- Service handles API errors gracefully

### Task 7.3: Add fallback formatter
- If LLM call fails, use deterministic summary

**Estimate:** 2 hours

**Acceptance Criteria:**
- System still sends results without LLM availability

### Task 7.4: Add summarizer tests
- Mock LLM response
- Validate fallback path

**Estimate:** 4 hours

**Acceptance Criteria:**
- Both normal and fallback paths are tested

---

## 20.8 Milestone 8: Main Orchestration

### Task 8.1: Implement logging setup
- Add `src/logging_setup.py`

**Estimate:** 2 hours

**Acceptance Criteria:**
- Logs include timestamps and event names

### Task 8.2: Implement `main.py`
- Load config
- For each enabled search:
  - fetch listings
  - filter listings
  - compare state
  - summarize
  - send message
  - update state

**Estimate:** 4 hours

**Acceptance Criteria:**
- End-to-end local run works with mocked services

### Task 8.3: Add CLI entry support
- Allow `python -m src.main` or `python src/main.py`

**Estimate:** 2 hours

**Acceptance Criteria:**
- Developer can run locally from documented command

---

## 20.9 Milestone 9: Deployment

### Task 9.1: Add GitHub Actions workflow
- Create `.github/workflows/listing_monitor.yml`
- Add schedule and manual trigger

**Estimate:** 3 hours

**Acceptance Criteria:**
- Workflow syntax validates
- Job installs dependencies and runs app

### Task 9.2: Add secrets documentation
- Document required GitHub secrets in `README.md`

**Estimate:** 1 hour

**Acceptance Criteria:**
- Another engineer can configure secrets from docs alone

### Task 9.3: Add deployment smoke test instructions
- Document how to run manually with `workflow_dispatch`

**Estimate:** 1 hour

**Acceptance Criteria:**
- Manual run steps are clear

---

## 20.10 Milestone 10: QA and Hardening

### Task 10.1: Add end-to-end dry run mode
- Add config or flag to skip Telegram sending
- Log message instead

**Estimate:** 3 hours

**Acceptance Criteria:**
- Developer can safely test without sending a real message

### Task 10.2: Add retry policy for provider calls
- Retry only safe network operations
- Keep retry count small

**Estimate:** 3 hours

**Acceptance Criteria:**
- Temporary network errors are retried
- Permanent failures do not retry forever

### Task 10.3: Add README setup guide
- local setup
- env vars
- config file
- run instructions
- test instructions
- deployment steps

**Estimate:** 4 hours

**Acceptance Criteria:**
- A new engineer can follow README without verbal help

---

## 21. Definition of Done

The MVP is done when:
- a scheduled GitHub Actions run executes successfully
- the app fetches listings from the configured provider
- filters are applied correctly
- only new or changed listings are selected
- a Telegram message is sent
- state is updated after a successful send
- tests pass
- README is complete

---

## 22. Risks and Mitigations

### Risk 1: Listing provider schema changes
**Mitigation:** isolate all mapping logic in one provider adapter

### Risk 2: LLM downtime or quota issues
**Mitigation:** deterministic fallback summary

### Risk 3: Telegram API failure
**Mitigation:** clear logging and retry only where safe

### Risk 4: Duplicate alerts
**Mitigation:** state table with listing ID and price/status tracking

### Risk 5: Junior engineer confusion
**Mitigation:** small modules, clear tasks, README, unit tests, strict scope

---

## 23. Future Enhancements

Not part of MVP, but likely next:
- support multiple providers
- support multiple Telegram chats
- support WhatsApp
- support daily digest vs instant alerts
- support favorite/ignore rules
- support ranking by commute, school score, HOA, etc.
- support images
- support web dashboard
- support map bounding boxes

---

## 24. Suggested Implementation Order

1. Bootstrap repo
2. Config + models
3. Provider adapter
4. Filtering
5. SQLite state
6. Deduplication
7. Telegram deterministic formatter
8. Main orchestration
9. LLM summarization
10. GitHub Actions
11. QA hardening

Do not start with the LLM.
Do not start with deployment.
Do not start with multiple providers.

Start with a local, deterministic pipeline first.

---

## 25. Notes for Codex

When implementing:
- prefer small, testable functions
- avoid large files
- add docstrings on public functions
- keep network code isolated
- mock all external APIs in unit tests
- do not hardcode secrets
- do not over-engineer abstractions beyond the provider/notifier/summarizer interfaces
- complete one milestone at a time
- after each milestone, update README with any new setup steps
