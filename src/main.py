"""Main orchestration entry point for the listing monitor workflow."""

from __future__ import annotations

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import logging
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from src.config import DEFAULT_SEARCHES_PATH, ConfigError, load_searches
from src.logging_setup import configure_logging, get_logger, log_event
from src.models import Listing, SearchConfig
from src.providers.base import ListingProvider, ProviderError
from src.providers.sample_provider import SampleListingProvider
from src.services.dedupe_service import classify_listings
from src.services.filter_service import filter_listings
from src.services.state_service import DEFAULT_DB_PATH, SQLiteStateService, StateError
from src.services.summarize_service import (
    ListingSummarizer,
    OpenAISummarizer,
    SummarizerError,
)
from src.services.telegram_service import Notifier, TelegramError, TelegramNotifier

LOGGER_NAME = "listing_monitor"


def run_listing_monitor(
    *,
    config_path: str | Path = DEFAULT_SEARCHES_PATH,
    state_db_path: str | Path = DEFAULT_DB_PATH,
    searches: Sequence[SearchConfig] | None = None,
    provider: ListingProvider | None = None,
    summarizer: ListingSummarizer | None = None,
    notifier: Notifier | None = None,
    state_service: SQLiteStateService | None = None,
    logger: logging.Logger | None = None,
) -> int:
    """Run the listing monitor once and return a process-friendly exit code."""

    app_logger = logger or get_logger(LOGGER_NAME)
    resolved_config_path = Path(config_path)
    resolved_db_path = Path(state_db_path)

    log_event(
        app_logger,
        logging.INFO,
        "run_started",
        config_path=resolved_config_path,
        db_path=resolved_db_path,
    )

    try:
        resolved_searches = list(searches) if searches is not None else load_searches(
            resolved_config_path
        )
        resolved_state_service = state_service or SQLiteStateService(resolved_db_path)
        resolved_state_service.bootstrap()
        resolved_provider = provider or SampleListingProvider()
        resolved_summarizer = summarizer or OpenAISummarizer()
        resolved_notifier = notifier or TelegramNotifier()
    except (ConfigError, ProviderError, SummarizerError, TelegramError, StateError) as exc:
        log_event(app_logger, logging.ERROR, "run_failed", error=str(exc))
        return 1

    enabled_searches = [search for search in resolved_searches if search.enabled]
    total_sent = 0
    search_failures = 0

    for search_config in enabled_searches:
        try:
            total_sent += _run_single_search(
                search_config=search_config,
                provider=resolved_provider,
                summarizer=resolved_summarizer,
                notifier=resolved_notifier,
                state_service=resolved_state_service,
                logger=app_logger,
            )
        except ProviderError as exc:
            search_failures += 1
            log_event(
                app_logger,
                logging.ERROR,
                "search_failed",
                search_name=search_config.search_name,
                error=str(exc),
            )
        except (StateError, SummarizerError, TelegramError) as exc:
            log_event(
                app_logger,
                logging.ERROR,
                "run_failed",
                search_name=search_config.search_name,
                error=str(exc),
            )
            return 1

    if search_failures:
        log_event(
            app_logger,
            logging.ERROR,
            "run_failed",
            searches_total=len(resolved_searches),
            enabled_searches=len(enabled_searches),
            searches_failed=search_failures,
            total_sent=total_sent,
        )
        return 1

    log_event(
        app_logger,
        logging.INFO,
        "run_complete",
        searches_total=len(resolved_searches),
        enabled_searches=len(enabled_searches),
        total_sent=total_sent,
    )
    return 0


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line interface for local runs."""

    parser = argparse.ArgumentParser(
        description="Run the real estate listing monitor once.",
    )
    parser.add_argument(
        "--config-path",
        default=str(DEFAULT_SEARCHES_PATH),
        help="Path to the YAML search configuration file.",
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="Path to the SQLite state database file.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python log level such as DEBUG, INFO, WARNING, or ERROR.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments, configure logging, and run the monitor."""

    parser = build_argument_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    configure_logging(args.log_level)
    return run_listing_monitor(
        config_path=args.config_path,
        state_db_path=args.db_path,
    )


def _run_single_search(
    *,
    search_config: SearchConfig,
    provider: ListingProvider,
    summarizer: ListingSummarizer,
    notifier: Notifier,
    state_service: SQLiteStateService,
    logger: logging.Logger,
) -> int:
    log_event(
        logger,
        logging.INFO,
        "search_started",
        search_name=search_config.search_name,
        location=search_config.location,
    )

    fetched_listings = provider.fetch_listings(search_config)
    log_event(
        logger,
        logging.INFO,
        "provider_fetch_complete",
        search_name=search_config.search_name,
        provider=_provider_name(provider),
        fetched=len(fetched_listings),
    )

    matched_listings = filter_listings(fetched_listings, search_config)
    log_event(
        logger,
        logging.INFO,
        "filter_complete",
        search_name=search_config.search_name,
        fetched=len(fetched_listings),
        matched=len(matched_listings),
    )

    existing_states = _load_existing_states(matched_listings, state_service)
    dedupe_results = classify_listings(matched_listings, existing_states)
    sendable_results = [result for result in dedupe_results if result.is_sendable]
    sendable_listings = [result.listing for result in sendable_results]

    log_event(
        logger,
        logging.INFO,
        "dedupe_complete",
        search_name=search_config.search_name,
        matched=len(matched_listings),
        changed=len(sendable_listings),
        new=sum(1 for result in sendable_results if result.classification == "new"),
        price_drop=sum(
            1 for result in sendable_results if "price_drop" in result.reasons
        ),
        status_change=sum(
            1 for result in sendable_results if "status_change" in result.reasons
        ),
        unchanged=sum(1 for result in dedupe_results if not result.is_sendable),
    )

    if not sendable_listings:
        log_event(
            logger,
            logging.INFO,
            "summary_complete",
            search_name=search_config.search_name,
            changed=0,
            skipped=True,
        )
        log_event(
            logger,
            logging.INFO,
            "telegram_send_complete",
            search_name=search_config.search_name,
            sent=0,
            skipped=True,
        )
        _persist_listing_state(
            matched_listings=matched_listings,
            sendable_listings=[],
            state_service=state_service,
        )
        return 0

    summary_text = summarizer.summarize(
        search_config.search_name,
        search_config,
        sendable_listings,
    )
    log_event(
        logger,
        logging.INFO,
        "summary_complete",
        search_name=search_config.search_name,
        changed=len(sendable_listings),
    )

    notifier.send_message(summary_text)
    log_event(
        logger,
        logging.INFO,
        "telegram_send_complete",
        search_name=search_config.search_name,
        sent=len(sendable_listings),
    )

    _persist_listing_state(
        matched_listings=matched_listings,
        sendable_listings=sendable_listings,
        state_service=state_service,
    )
    return len(sendable_listings)


def _load_existing_states(
    listings: Sequence[Listing],
    state_service: SQLiteStateService,
) -> dict[tuple[str, str], object]:
    existing_states: dict[tuple[str, str], object] = {}

    for listing in listings:
        listing_state = state_service.get_listing_state(
            listing_id=listing.listing_id,
            search_name=listing.search_name,
        )
        if listing_state is None:
            continue

        existing_states[(listing.search_name, listing.listing_id)] = listing_state

    return existing_states


def _persist_listing_state(
    *,
    matched_listings: Sequence[Listing],
    sendable_listings: Sequence[Listing],
    state_service: SQLiteStateService,
) -> None:
    sent_listing_ids = {listing.listing_id for listing in sendable_listings}
    sent_at = _current_timestamp() if sent_listing_ids else None

    for listing in matched_listings:
        upsert_kwargs: dict[str, object] = {
            "listing_id": listing.listing_id,
            "search_name": listing.search_name,
            "last_seen_price": listing.price,
            "last_seen_status": listing.status,
        }
        if listing.listing_id in sent_listing_ids:
            upsert_kwargs["last_sent_at"] = sent_at

        state_service.upsert_listing_state(**upsert_kwargs)


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _provider_name(provider: ListingProvider) -> str:
    provider_name = getattr(provider, "provider_name", "")
    if isinstance(provider_name, str) and provider_name.strip():
        return provider_name.strip()
    return provider.__class__.__name__


if __name__ == "__main__":
    raise SystemExit(main())
