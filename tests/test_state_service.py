from pathlib import Path

from src.services.state_service import SQLiteStateService


def test_state_service_upserts_and_reads_listing_state(tmp_path: Path) -> None:
    db_path = tmp_path / "listing_state.db"
    service = SQLiteStateService(db_path)

    inserted_state = service.upsert_listing_state(
        listing_id="listing-123",
        search_name="triangle_homes",
        last_seen_price=399000,
        last_seen_status="active",
        last_sent_at="2026-03-17T12:00:00+00:00",
        first_seen_at="2026-03-16T08:00:00+00:00",
        updated_at="2026-03-17T12:00:00+00:00",
    )

    fetched_after_insert = service.get_listing_state(
        listing_id="listing-123",
        search_name="triangle_homes",
    )

    updated_state = service.upsert_listing_state(
        listing_id="listing-123",
        search_name="triangle_homes",
        last_seen_price=389000,
        last_seen_status="pending",
        updated_at="2026-03-18T09:30:00+00:00",
    )

    fetched_after_update = service.get_listing_state(
        listing_id="listing-123",
        search_name="triangle_homes",
    )

    assert inserted_state.last_seen_price == 399000
    assert fetched_after_insert == inserted_state

    assert updated_state.last_seen_price == 389000
    assert updated_state.last_seen_status == "pending"
    assert updated_state.last_sent_at == "2026-03-17T12:00:00+00:00"
    assert updated_state.first_seen_at == "2026-03-16T08:00:00+00:00"
    assert updated_state.updated_at == "2026-03-18T09:30:00+00:00"
    assert fetched_after_update == updated_state


def test_state_service_returns_none_for_missing_listing_state(tmp_path: Path) -> None:
    service = SQLiteStateService(tmp_path / "listing_state.db")

    state = service.get_listing_state(
        listing_id="missing-listing",
        search_name="triangle_homes",
    )

    assert state is None
