import logging

from src.main import run_listing_monitor
from src.models import Listing, SearchConfig
from src.providers.base import ProviderError
from src.services.state_service import ListingState
from src.services.telegram_service import TelegramError


class FakeProvider:
    def __init__(self, responses: dict[str, list[Listing] | Exception]) -> None:
        self._responses = responses
        self.calls: list[str] = []

    def fetch_listings(self, search_config: SearchConfig) -> list[Listing]:
        self.calls.append(search_config.search_name)
        response = self._responses[search_config.search_name]
        if isinstance(response, Exception):
            raise response
        return response


class FakeSummarizer:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def summarize(
        self,
        search_name: str,
        criteria: SearchConfig,
        listings: list[Listing],
    ) -> str:
        self.calls.append(
            {
                "search_name": search_name,
                "criteria": criteria,
                "listings": listings,
            }
        )
        return f"Summary for {search_name}: {len(listings)} listing(s)"


class FakeNotifier:
    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.messages: list[str] = []

    def send_message(self, message: str) -> None:
        if self._error is not None:
            raise self._error
        self.messages.append(message)


class FakeStateService:
    def __init__(self, initial_states: list[ListingState] | None = None) -> None:
        self.bootstrap_called = False
        self.upsert_calls: list[dict[str, object]] = []
        self.states = {
            (state.search_name, state.listing_id): state
            for state in (initial_states or [])
        }

    def bootstrap(self) -> None:
        self.bootstrap_called = True

    def get_listing_state(
        self,
        *,
        listing_id: str,
        search_name: str,
    ) -> ListingState | None:
        return self.states.get((search_name, listing_id))

    def upsert_listing_state(
        self,
        *,
        listing_id: str,
        search_name: str,
        last_seen_price: int | None,
        last_seen_status: str | None,
        last_sent_at: str | None = None,
    ) -> ListingState:
        self.upsert_calls.append(
            {
                "listing_id": listing_id,
                "search_name": search_name,
                "last_seen_price": last_seen_price,
                "last_seen_status": last_seen_status,
                "last_sent_at": last_sent_at,
            }
        )

        existing_state = self.states.get((search_name, listing_id))
        resolved_last_sent_at = (
            last_sent_at
            if last_sent_at is not None
            else existing_state.last_sent_at if existing_state is not None else None
        )
        resolved_state = ListingState(
            listing_id=listing_id,
            search_name=search_name,
            last_seen_price=last_seen_price,
            last_seen_status=last_seen_status,
            last_sent_at=resolved_last_sent_at,
            first_seen_at=(
                existing_state.first_seen_at
                if existing_state is not None
                else "2026-03-17T12:00:00+00:00"
            ),
            updated_at="2026-03-17T12:00:00+00:00",
        )
        self.states[(search_name, listing_id)] = resolved_state
        return resolved_state


def test_run_listing_monitor_orchestrates_enabled_searches_and_updates_state_after_send(
    caplog,
) -> None:
    enabled_search = build_search_config()
    disabled_search = build_search_config(
        search_name="disabled_search",
        enabled=False,
        location="Raleigh, NC",
    )
    new_listing = build_listing(listing_id="listing-new", price=395000)
    unchanged_listing = build_listing(
        listing_id="listing-existing",
        price=410000,
        address="456 Oak Ave",
        url="https://example.com/listings/listing-existing",
    )
    provider = FakeProvider(
        {
            enabled_search.search_name: [new_listing, unchanged_listing],
            disabled_search.search_name: [build_listing(listing_id="listing-disabled")],
        }
    )
    summarizer = FakeSummarizer()
    notifier = FakeNotifier()
    state_service = FakeStateService(
        [
            build_state(
                listing_id="listing-existing",
                search_name=enabled_search.search_name,
                last_seen_price=399000,
                last_seen_status="active",
                last_sent_at="2026-03-16T08:00:00+00:00",
            )
        ]
    )
    logger = logging.getLogger("tests.test_main.success")

    caplog.set_level(logging.INFO, logger=logger.name)
    exit_code = run_listing_monitor(
        searches=[enabled_search, disabled_search],
        provider=provider,
        summarizer=summarizer,
        notifier=notifier,
        state_service=state_service,
        logger=logger,
    )

    assert exit_code == 0
    assert provider.calls == ["triangle_homes"]
    assert state_service.bootstrap_called is True
    assert len(summarizer.calls) == 1
    assert summarizer.calls[0]["search_name"] == "triangle_homes"
    assert summarizer.calls[0]["listings"] == [new_listing]
    assert notifier.messages == ["Summary for triangle_homes: 1 listing(s)"]
    assert len(state_service.upsert_calls) == 2
    assert state_service.states[("triangle_homes", "listing-new")].last_sent_at is not None
    assert (
        state_service.states[("triangle_homes", "listing-existing")].last_sent_at
        == "2026-03-16T08:00:00+00:00"
    )
    assert (
        state_service.states[("triangle_homes", "listing-existing")].last_seen_price
        == 410000
    )
    assert "event=run_complete" in caplog.text
    assert "event=provider_fetch_complete" in caplog.text
    assert "event=telegram_send_complete" in caplog.text


def test_run_listing_monitor_continues_after_provider_error_and_marks_run_failed(
    caplog,
) -> None:
    broken_search = build_search_config(search_name="broken_search", location="Apex, NC")
    healthy_search = build_search_config(search_name="healthy_search", location="Cary, NC")
    provider = FakeProvider(
        {
            broken_search.search_name: ProviderError("Provider outage for broken_search"),
            healthy_search.search_name: [build_listing(search_name="healthy_search")],
        }
    )
    summarizer = FakeSummarizer()
    notifier = FakeNotifier()
    state_service = FakeStateService()
    logger = logging.getLogger("tests.test_main.provider_failure")

    caplog.set_level(logging.INFO, logger=logger.name)
    exit_code = run_listing_monitor(
        searches=[broken_search, healthy_search],
        provider=provider,
        summarizer=summarizer,
        notifier=notifier,
        state_service=state_service,
        logger=logger,
    )

    assert exit_code == 1
    assert provider.calls == ["broken_search", "healthy_search"]
    assert notifier.messages == ["Summary for healthy_search: 1 listing(s)"]
    assert len(summarizer.calls) == 1
    assert summarizer.calls[0]["search_name"] == "healthy_search"
    assert "event=search_failed" in caplog.text
    assert 'search_name="broken_search"' in caplog.text
    assert "event=run_failed" in caplog.text


def test_run_listing_monitor_does_not_update_state_when_telegram_send_fails(
    caplog,
) -> None:
    search_config = build_search_config()
    provider = FakeProvider(
        {
            search_config.search_name: [build_listing()],
        }
    )
    summarizer = FakeSummarizer()
    notifier = FakeNotifier(TelegramError("Telegram sendMessage request failed."))
    state_service = FakeStateService()
    logger = logging.getLogger("tests.test_main.telegram_failure")

    caplog.set_level(logging.INFO, logger=logger.name)
    exit_code = run_listing_monitor(
        searches=[search_config],
        provider=provider,
        summarizer=summarizer,
        notifier=notifier,
        state_service=state_service,
        logger=logger,
    )

    assert exit_code == 1
    assert len(summarizer.calls) == 1
    assert state_service.upsert_calls == []
    assert "event=run_failed" in caplog.text
    assert "Telegram sendMessage request failed." in caplog.text


def build_search_config(**overrides: object) -> SearchConfig:
    values = {
        "search_name": "triangle_homes",
        "enabled": True,
        "location": "Durham, NC",
        "max_price": 450000,
        "min_beds": 3.0,
        "min_baths": 2.0,
        "property_types": ["single_family", "townhome"],
        "max_hoa": None,
        "min_sqft": None,
        "keywords_include": [],
        "keywords_exclude": [],
    }
    values.update(overrides)
    return SearchConfig(**values)


def build_listing(**overrides: object) -> Listing:
    values = {
        "listing_id": "listing-123",
        "search_name": "triangle_homes",
        "address": "123 Main St",
        "city": "Durham",
        "state": "NC",
        "zip_code": "27701",
        "price": 399000,
        "beds": 3.0,
        "baths": 2.5,
        "sqft": 1800,
        "property_type": "single_family",
        "hoa_monthly": 125,
        "status": "active",
        "url": "https://example.com/listings/listing-123",
        "description": "Updated kitchen and fenced yard.",
        "provider_name": "sample_provider",
        "raw_payload": {"id": "listing-123"},
    }
    values.update(overrides)
    return Listing(**values)


def build_state(
    *,
    listing_id: str,
    search_name: str,
    last_seen_price: int | None,
    last_seen_status: str | None,
    last_sent_at: str | None,
) -> ListingState:
    return ListingState(
        listing_id=listing_id,
        search_name=search_name,
        last_seen_price=last_seen_price,
        last_seen_status=last_seen_status,
        last_sent_at=last_sent_at,
        first_seen_at="2026-03-16T12:00:00+00:00",
        updated_at="2026-03-16T12:00:00+00:00",
    )
