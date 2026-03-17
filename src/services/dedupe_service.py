"""Deterministic deduplication helpers for normalized listings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from src.models import Listing
from src.services.state_service import ListingState

ListingStateKey = tuple[str, str]


@dataclass(slots=True, frozen=True)
class DedupeResult:
    """Classification result for one listing compared with persisted state."""

    listing: Listing
    existing_state: ListingState | None
    classification: str
    is_sendable: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


def classify_listing(
    listing: Listing,
    existing_state: ListingState | None,
) -> DedupeResult:
    """Classify a listing as new, changed, or unchanged."""

    if existing_state is None:
        return DedupeResult(
            listing=listing,
            existing_state=None,
            classification="new",
            is_sendable=True,
            reasons=("new",),
        )

    reasons: list[str] = []

    if _is_price_drop(listing.price, existing_state.last_seen_price):
        reasons.append("price_drop")

    if _status_changed(listing.status, existing_state.last_seen_status):
        reasons.append("status_change")

    if not reasons:
        return DedupeResult(
            listing=listing,
            existing_state=existing_state,
            classification="unchanged",
            is_sendable=False,
            reasons=(),
        )

    return DedupeResult(
        listing=listing,
        existing_state=existing_state,
        classification=reasons[0],
        is_sendable=True,
        reasons=tuple(reasons),
    )


def classify_listings(
    listings: list[Listing],
    existing_states: Mapping[ListingStateKey, ListingState],
) -> list[DedupeResult]:
    """Classify listings in input order using an in-memory state mapping."""

    return [
        classify_listing(
            listing,
            existing_states.get((listing.search_name, listing.listing_id)),
        )
        for listing in listings
    ]


def _is_price_drop(current_price: int, previous_price: int | None) -> bool:
    if previous_price is None:
        return False

    return current_price < previous_price


def _status_changed(current_status: str | None, previous_status: str | None) -> bool:
    return current_status != previous_status
