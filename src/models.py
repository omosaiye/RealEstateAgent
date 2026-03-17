"""Application data models for the real estate listing monitor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RawPayload = dict[str, Any]


@dataclass(slots=True)
class SearchConfig:
    """User-defined search criteria loaded from ``config/searches.yaml``.

    Attributes:
        search_name: Stable name used in logs and persisted state.
        enabled: Whether the search should run.
        location: Human-readable area string sent to the provider.
        max_price: Maximum allowed listing price in whole dollars.
        min_beds: Minimum bedroom count required for a match.
        min_baths: Minimum bathroom count required for a match.
        property_types: Allowed property type names such as ``single_family``.
        max_hoa: Optional maximum monthly HOA fee.
        min_sqft: Optional minimum square footage.
        keywords_include: Optional keywords a listing should include.
        keywords_exclude: Optional keywords a listing should exclude.
    """

    search_name: str
    enabled: bool
    location: str
    max_price: int
    min_beds: float
    min_baths: float
    property_types: list[str]
    max_hoa: int | None = None
    min_sqft: int | None = None
    keywords_include: list[str] = field(default_factory=list)
    keywords_exclude: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Listing:
    """Normalized real estate listing returned by provider adapters.

    Attributes:
        listing_id: Provider-specific unique listing identifier.
        search_name: Search configuration name that produced the listing.
        address: Street address or best available address text.
        city: Listing city.
        state: Listing state or province code.
        zip_code: Postal code when available.
        price: Current listing price in whole dollars.
        beds: Bedroom count when available.
        baths: Bathroom count when available.
        sqft: Square footage when available.
        property_type: Normalized property type name.
        hoa_monthly: Monthly HOA fee when available.
        status: Listing status such as ``active`` or ``pending``.
        url: Direct provider URL for the listing.
        description: Provider description text when available.
        provider_name: Source provider name used for logging and debugging.
        raw_payload: Original provider payload for debugging and inspection.
    """

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
    raw_payload: RawPayload = field(default_factory=dict)
