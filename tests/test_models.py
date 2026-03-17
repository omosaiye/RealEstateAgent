from src.models import Listing, SearchConfig


def test_search_config_can_be_created_with_optional_defaults() -> None:
    search = SearchConfig(
        search_name="triangle_homes",
        enabled=True,
        location="Durham, NC",
        max_price=400000,
        min_beds=3.0,
        min_baths=2.0,
        property_types=["single_family"],
    )

    assert search.max_hoa is None
    assert search.min_sqft is None
    assert search.keywords_include == []
    assert search.keywords_exclude == []


def test_listing_can_be_instantiated() -> None:
    listing = Listing(
        listing_id="listing-123",
        search_name="triangle_homes",
        address="123 Main St",
        city="Durham",
        state="NC",
        zip_code="27701",
        price=399000,
        beds=3.0,
        baths=2.5,
        sqft=1800,
        property_type="single_family",
        hoa_monthly=125,
        status="active",
        url="https://example.com/listings/listing-123",
        description="Updated kitchen and fenced yard.",
        provider_name="sample_provider",
        raw_payload={"id": "listing-123"},
    )

    assert listing.listing_id == "listing-123"
    assert listing.search_name == "triangle_homes"
    assert listing.raw_payload == {"id": "listing-123"}
