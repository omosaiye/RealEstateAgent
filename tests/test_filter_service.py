from src.models import Listing, SearchConfig
from src.services.filter_service import filter_listings, listing_matches_search


def test_filter_listings_returns_only_listings_that_match_all_filters() -> None:
    search_config = build_search_config()
    matching_listing = build_listing()
    too_expensive_listing = build_listing(listing_id="listing-2", price=500001)
    excluded_keyword_listing = build_listing(
        listing_id="listing-3",
        description="Garage included, but this is an auction sale.",
    )

    filtered_listings = filter_listings(
        [matching_listing, too_expensive_listing, excluded_keyword_listing],
        search_config,
    )

    assert filtered_listings == [matching_listing]


def test_listing_matches_search_accepts_values_on_exact_numeric_boundaries() -> None:
    search_config = build_search_config()
    listing = build_listing(
        price=450000,
        beds=3.0,
        baths=2.0,
        hoa_monthly=250,
        sqft=1600,
    )

    assert listing_matches_search(listing, search_config) is True


def test_listing_matches_search_rejects_listing_below_minimum_beds() -> None:
    search_config = build_search_config()
    listing = build_listing(beds=2.0)

    assert listing_matches_search(listing, search_config) is False


def test_listing_matches_search_rejects_listing_below_minimum_baths() -> None:
    search_config = build_search_config()
    listing = build_listing(baths=1.5)

    assert listing_matches_search(listing, search_config) is False


def test_listing_matches_search_normalizes_property_type_case() -> None:
    search_config = build_search_config()
    listing = build_listing(property_type="Single_Family")

    assert listing_matches_search(listing, search_config) is True


def test_listing_matches_search_rejects_listing_when_optional_hoa_filter_is_set_and_missing() -> None:
    search_config = build_search_config()
    listing = build_listing(hoa_monthly=None)

    assert listing_matches_search(listing, search_config) is False


def test_listing_matches_search_rejects_listing_when_optional_sqft_filter_is_set_and_missing() -> None:
    search_config = build_search_config()
    listing = build_listing(sqft=None)

    assert listing_matches_search(listing, search_config) is False


def test_listing_matches_search_requires_all_include_keywords_case_insensitively() -> None:
    search_config = build_search_config(
        keywords_include=["garage", "fenced yard"],
        keywords_exclude=[],
    )
    listing = build_listing(description="Attached GARAGE with a fenced yard.")

    assert listing_matches_search(listing, search_config) is True


def test_listing_matches_search_rejects_listing_that_contains_excluded_keyword_case_insensitively() -> None:
    search_config = build_search_config()
    listing = build_listing(description="Spacious townhome offered as an AUCTION.")

    assert listing_matches_search(listing, search_config) is False


def test_listing_matches_search_rejects_listing_when_include_keyword_is_missing() -> None:
    search_config = build_search_config(
        keywords_include=["garage", "pool"],
        keywords_exclude=[],
    )
    listing = build_listing(description="Garage parking, updated kitchen.")

    assert listing_matches_search(listing, search_config) is False


def test_listing_matches_search_handles_missing_description_when_keyword_filters_are_empty() -> None:
    search_config = build_search_config(
        keywords_include=[],
        keywords_exclude=[],
    )
    listing = build_listing(description=None)

    assert listing_matches_search(listing, search_config) is True


def test_listing_matches_search_rejects_listing_with_missing_property_type() -> None:
    search_config = build_search_config()
    listing = build_listing(property_type=None)

    assert listing_matches_search(listing, search_config) is False


def test_listing_matches_search_rejects_listing_with_missing_beds() -> None:
    search_config = build_search_config()
    listing = build_listing(beds=None)

    assert listing_matches_search(listing, search_config) is False


def test_listing_matches_search_rejects_listing_with_missing_baths() -> None:
    search_config = build_search_config()
    listing = build_listing(baths=None)

    assert listing_matches_search(listing, search_config) is False


def build_search_config(
    *,
    keywords_include: list[str] | None = None,
    keywords_exclude: list[str] | None = None,
) -> SearchConfig:
    return SearchConfig(
        search_name="raleigh_primary",
        enabled=True,
        location="Raleigh, NC",
        max_price=450000,
        min_beds=3.0,
        min_baths=2.0,
        property_types=["single_family", "townhome"],
        max_hoa=250,
        min_sqft=1600,
        keywords_include=keywords_include if keywords_include is not None else ["garage"],
        keywords_exclude=keywords_exclude if keywords_exclude is not None else ["auction"],
    )


def build_listing(
    *,
    listing_id: str = "listing-1",
    price: int = 425000,
    beds: float | None = 3.0,
    baths: float | None = 2.5,
    sqft: int | None = 1800,
    property_type: str | None = "single_family",
    hoa_monthly: int | None = 200,
    description: str | None = "Attached garage, updated kitchen, fenced yard.",
) -> Listing:
    return Listing(
        listing_id=listing_id,
        search_name="raleigh_primary",
        address="123 Main St",
        city="Raleigh",
        state="NC",
        zip_code="27601",
        price=price,
        beds=beds,
        baths=baths,
        sqft=sqft,
        property_type=property_type,
        hoa_monthly=hoa_monthly,
        status="active",
        url=f"https://example.com/listings/{listing_id}",
        description=description,
        provider_name="sample_provider",
        raw_payload={"id": listing_id},
    )
