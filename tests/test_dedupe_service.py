from src.models import Listing
from src.services.dedupe_service import classify_listing
from src.services.state_service import ListingState


def test_classify_listing_marks_new_listing_as_sendable() -> None:
    result = classify_listing(_build_listing(), None)

    assert result.classification == "new"
    assert result.is_sendable is True
    assert result.reasons == ("new",)


def test_classify_listing_marks_unchanged_listing_as_not_sendable() -> None:
    listing = _build_listing(price=399000, status="active")
    existing_state = _build_state(last_seen_price=399000, last_seen_status="active")

    result = classify_listing(listing, existing_state)

    assert result.classification == "unchanged"
    assert result.is_sendable is False
    assert result.reasons == ()


def test_classify_listing_marks_price_drop_as_sendable() -> None:
    listing = _build_listing(price=385000, status="active")
    existing_state = _build_state(last_seen_price=399000, last_seen_status="active")

    result = classify_listing(listing, existing_state)

    assert result.classification == "price_drop"
    assert result.is_sendable is True
    assert result.reasons == ("price_drop",)


def test_classify_listing_marks_status_change_as_sendable() -> None:
    listing = _build_listing(price=399000, status="pending")
    existing_state = _build_state(last_seen_price=399000, last_seen_status="active")

    result = classify_listing(listing, existing_state)

    assert result.classification == "status_change"
    assert result.is_sendable is True
    assert result.reasons == ("status_change",)


def _build_listing(*, price: int = 399000, status: str | None = "active") -> Listing:
    return Listing(
        listing_id="listing-123",
        search_name="triangle_homes",
        address="123 Main St",
        city="Durham",
        state="NC",
        zip_code="27701",
        price=price,
        beds=3.0,
        baths=2.5,
        sqft=1800,
        property_type="single_family",
        hoa_monthly=125,
        status=status,
        url="https://example.com/listings/listing-123",
        description="Updated kitchen and fenced yard.",
        provider_name="sample_provider",
        raw_payload={"id": "listing-123"},
    )


def _build_state(
    *,
    last_seen_price: int | None,
    last_seen_status: str | None,
) -> ListingState:
    return ListingState(
        listing_id="listing-123",
        search_name="triangle_homes",
        last_seen_price=last_seen_price,
        last_seen_status=last_seen_status,
        last_sent_at="2026-03-17T12:00:00+00:00",
        first_seen_at="2026-03-16T12:00:00+00:00",
        updated_at="2026-03-17T12:00:00+00:00",
    )
