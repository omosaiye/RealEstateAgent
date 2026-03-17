"""Deterministic filtering for normalized real estate listings.

Keyword filters use case-insensitive substring matching across the listing's
available text fields. This keeps the behavior simple and predictable while
still working when some optional text fields are missing.
"""

from __future__ import annotations

from src.models import Listing, SearchConfig


def filter_listings(
    listings: list[Listing],
    search_config: SearchConfig,
) -> list[Listing]:
    """Return only the listings that match the supplied search criteria."""

    return [
        listing
        for listing in listings
        if listing_matches_search(listing, search_config)
    ]


def listing_matches_search(listing: Listing, search_config: SearchConfig) -> bool:
    """Return ``True`` when a listing satisfies all configured filters."""

    return (
        _matches_max_price(listing, search_config)
        and _matches_min_beds(listing, search_config)
        and _matches_min_baths(listing, search_config)
        and _matches_property_type(listing, search_config)
        and _matches_max_hoa(listing, search_config)
        and _matches_min_sqft(listing, search_config)
        and _matches_keywords_include(listing, search_config)
        and _matches_keywords_exclude(listing, search_config)
    )


def _matches_max_price(listing: Listing, search_config: SearchConfig) -> bool:
    return listing.price <= search_config.max_price


def _matches_min_beds(listing: Listing, search_config: SearchConfig) -> bool:
    return listing.beds is not None and listing.beds >= search_config.min_beds


def _matches_min_baths(listing: Listing, search_config: SearchConfig) -> bool:
    return listing.baths is not None and listing.baths >= search_config.min_baths


def _matches_property_type(listing: Listing, search_config: SearchConfig) -> bool:
    listing_property_type = _normalize_text(listing.property_type)
    if listing_property_type is None:
        return False

    allowed_property_types = {
        normalized_value
        for property_type in search_config.property_types
        if (normalized_value := _normalize_text(property_type)) is not None
    }
    return listing_property_type in allowed_property_types


def _matches_max_hoa(listing: Listing, search_config: SearchConfig) -> bool:
    if search_config.max_hoa is None:
        return True
    return listing.hoa_monthly is not None and listing.hoa_monthly <= search_config.max_hoa


def _matches_min_sqft(listing: Listing, search_config: SearchConfig) -> bool:
    if search_config.min_sqft is None:
        return True
    return listing.sqft is not None and listing.sqft >= search_config.min_sqft


def _matches_keywords_include(listing: Listing, search_config: SearchConfig) -> bool:
    if not search_config.keywords_include:
        return True

    searchable_text = _build_searchable_text(listing)
    return all(keyword.lower() in searchable_text for keyword in search_config.keywords_include)


def _matches_keywords_exclude(listing: Listing, search_config: SearchConfig) -> bool:
    if not search_config.keywords_exclude:
        return True

    searchable_text = _build_searchable_text(listing)
    return not any(
        keyword.lower() in searchable_text for keyword in search_config.keywords_exclude
    )


def _build_searchable_text(listing: Listing) -> str:
    text_parts = (
        listing.address,
        listing.city,
        listing.state,
        listing.zip_code,
        listing.property_type,
        listing.description,
    )
    return " ".join(part.lower() for part in text_parts if part)


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None

    normalized_value = value.strip().lower()
    if not normalized_value:
        return None

    return normalized_value
