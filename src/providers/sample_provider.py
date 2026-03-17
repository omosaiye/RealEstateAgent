"""Sample provider adapter that normalizes API results into ``Listing`` objects."""

from __future__ import annotations

import os
from typing import Any

import httpx

from src.models import Listing, RawPayload, SearchConfig
from src.providers.base import ListingProvider, ProviderError

DEFAULT_SAMPLE_PROVIDER_URL = "https://api.example.com/v1/listings"
DEFAULT_TIMEOUT_SECONDS = 10.0


class SampleListingProvider(ListingProvider):
    """Simple HTTP provider adapter for a sample listings API.

    Expected response shape::

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
                    "description": "Updated kitchen and fenced yard."
                }
            ]
        }
    """

    provider_name = "sample_provider"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_SAMPLE_PROVIDER_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = _resolve_api_key(api_key)
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._client = client

    def fetch_listings(self, search_config: SearchConfig) -> list[Listing]:
        """Fetch and normalize provider results for a single search."""

        payload = self._fetch_payload(search_config)
        raw_results = _extract_results(payload)

        return [
            _normalize_listing(raw_listing, search_config, self.provider_name)
            for raw_listing in raw_results
        ]

    def _fetch_payload(self, search_config: SearchConfig) -> dict[str, Any]:
        params = {"location": search_config.location}
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }

        try:
            if self._client is not None:
                response = self._client.get(
                    self._base_url,
                    params=params,
                    headers=headers,
                    timeout=self._timeout_seconds,
                )
            else:
                with httpx.Client() as client:
                    response = client.get(
                        self._base_url,
                        params=params,
                        headers=headers,
                        timeout=self._timeout_seconds,
                    )

            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "Sample provider request timed out after "
                f"{self._timeout_seconds} seconds for search "
                f"'{search_config.search_name}'."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                "Sample provider request failed with status "
                f"{exc.response.status_code} for search "
                f"'{search_config.search_name}'."
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Sample provider request failed for search '{search_config.search_name}'."
            ) from exc
        except ValueError as exc:
            raise ProviderError(
                f"Sample provider returned invalid JSON for search '{search_config.search_name}'."
            ) from exc

        if payload is None:
            return {}

        if not isinstance(payload, dict):
            raise ProviderError("Sample provider response must be a JSON object.")

        return payload


def _resolve_api_key(api_key: str | None) -> str:
    resolved_api_key = api_key or os.getenv("LISTING_PROVIDER_API_KEY", "").strip()
    if not resolved_api_key:
        raise ProviderError(
            "LISTING_PROVIDER_API_KEY environment variable is required for "
            "SampleListingProvider."
        )
    return resolved_api_key


def _extract_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_results = payload.get("results")
    if raw_results is None:
        return []

    if not isinstance(raw_results, list):
        raise ProviderError("Sample provider response field 'results' must be a list.")

    normalized_results: list[dict[str, Any]] = []
    for raw_listing in raw_results:
        if not isinstance(raw_listing, dict):
            raise ProviderError("Each sample provider listing must be a JSON object.")
        normalized_results.append(raw_listing)

    return normalized_results


def _normalize_listing(
    raw_listing: RawPayload,
    search_config: SearchConfig,
    provider_name: str,
) -> Listing:
    listing_id = _require_string(raw_listing, "id")
    address = _require_string(raw_listing, "address")
    city = _require_string(raw_listing, "city")
    state = _require_string(raw_listing, "state")
    price = _require_int(raw_listing, "price")
    url = _require_string(raw_listing, "url")

    return Listing(
        listing_id=listing_id,
        search_name=search_config.search_name,
        address=address,
        city=city,
        state=state,
        zip_code=_optional_string(raw_listing, "zip_code"),
        price=price,
        beds=_optional_number(raw_listing, "beds"),
        baths=_optional_number(raw_listing, "baths"),
        sqft=_optional_int(raw_listing, "sqft"),
        property_type=_optional_string(raw_listing, "property_type"),
        hoa_monthly=_optional_int(raw_listing, "hoa_monthly"),
        status=_optional_string(raw_listing, "status"),
        url=url,
        description=_optional_string(raw_listing, "description"),
        provider_name=provider_name,
        raw_payload=dict(raw_listing),
    )


def _require_string(raw_listing: RawPayload, field_name: str) -> str:
    value = raw_listing.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ProviderError(
            f"Sample provider listing field '{field_name}' must be a non-empty string."
        )
    return value.strip()


def _optional_string(raw_listing: RawPayload, field_name: str) -> str | None:
    value = raw_listing.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProviderError(
            f"Sample provider listing field '{field_name}' must be a string when present."
        )

    normalized_value = value.strip()
    return normalized_value or None


def _require_int(raw_listing: RawPayload, field_name: str) -> int:
    value = raw_listing.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProviderError(
            f"Sample provider listing field '{field_name}' must be an integer."
        )
    return value


def _optional_int(raw_listing: RawPayload, field_name: str) -> int | None:
    value = raw_listing.get(field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProviderError(
            f"Sample provider listing field '{field_name}' must be an integer when present."
        )
    return value


def _optional_number(raw_listing: RawPayload, field_name: str) -> float | None:
    value = raw_listing.get(field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ProviderError(
            f"Sample provider listing field '{field_name}' must be numeric when present."
        )
    return float(value)
