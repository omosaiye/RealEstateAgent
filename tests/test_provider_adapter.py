import httpx
import pytest

from src.models import SearchConfig
from src.providers.base import ProviderError
from src.providers.sample_provider import SampleListingProvider


class SpyHttpClient:
    def __init__(self, payload: object) -> None:
        self._payload = payload
        self.calls: list[dict[str, object]] = []

    def get(
        self,
        url: str,
        *,
        params: dict[str, object],
        headers: dict[str, str],
        timeout: float,
    ) -> httpx.Response:
        self.calls.append(
            {
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": timeout,
            }
        )
        request = httpx.Request("GET", url, params=params, headers=headers)
        return httpx.Response(200, json=self._payload, request=request)


@pytest.fixture
def search_config() -> SearchConfig:
    return SearchConfig(
        search_name="triangle_homes",
        enabled=True,
        location="Durham, NC",
        max_price=450000,
        min_beds=3.0,
        min_baths=2.0,
        property_types=["single_family", "townhome"],
    )


def test_sample_provider_normalizes_results_into_listing_objects(
    search_config: SearchConfig,
) -> None:
    client = SpyHttpClient(
        {
            "results": [
                {
                    "id": "listing-123",
                    "address": "123 Main St",
                    "city": "Durham",
                    "state": "NC",
                    "zip_code": "27701",
                    "price": 399000,
                    "beds": 3,
                    "baths": 2.5,
                    "sqft": 1800,
                    "property_type": "single_family",
                    "hoa_monthly": 125,
                    "status": "active",
                    "url": "https://example.com/listings/listing-123",
                    "description": "Updated kitchen and fenced yard.",
                }
            ]
        }
    )
    provider = SampleListingProvider(
        api_key="test-api-key",
        client=client,
        timeout_seconds=7.5,
    )

    listings = provider.fetch_listings(search_config)

    assert len(listings) == 1
    listing = listings[0]
    assert listing.listing_id == "listing-123"
    assert listing.search_name == "triangle_homes"
    assert listing.address == "123 Main St"
    assert listing.city == "Durham"
    assert listing.state == "NC"
    assert listing.zip_code == "27701"
    assert listing.price == 399000
    assert listing.beds == 3.0
    assert listing.baths == 2.5
    assert listing.sqft == 1800
    assert listing.property_type == "single_family"
    assert listing.hoa_monthly == 125
    assert listing.status == "active"
    assert listing.url == "https://example.com/listings/listing-123"
    assert listing.description == "Updated kitchen and fenced yard."
    assert listing.provider_name == "sample_provider"
    assert listing.raw_payload == {
        "id": "listing-123",
        "address": "123 Main St",
        "city": "Durham",
        "state": "NC",
        "zip_code": "27701",
        "price": 399000,
        "beds": 3,
        "baths": 2.5,
        "sqft": 1800,
        "property_type": "single_family",
        "hoa_monthly": 125,
        "status": "active",
        "url": "https://example.com/listings/listing-123",
        "description": "Updated kitchen and fenced yard.",
    }
    assert client.calls == [
        {
            "url": "https://api.example.com/v1/listings",
            "params": {"location": "Durham, NC"},
            "headers": {
                "Authorization": "Bearer test-api-key",
                "Accept": "application/json",
            },
            "timeout": 7.5,
        }
    ]


def test_sample_provider_returns_empty_list_for_empty_results(
    search_config: SearchConfig,
) -> None:
    provider = SampleListingProvider(
        api_key="test-api-key",
        client=SpyHttpClient({"results": []}),
    )

    listings = provider.fetch_listings(search_config)

    assert listings == []


def test_sample_provider_requires_provider_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LISTING_PROVIDER_API_KEY", raising=False)

    with pytest.raises(
        ProviderError,
        match="LISTING_PROVIDER_API_KEY environment variable is required",
    ):
        SampleListingProvider()
