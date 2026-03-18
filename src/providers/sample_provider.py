"""RentCast provider adapter that normalizes API results into ``Listing`` objects."""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable
from typing import Any

import httpx

from src.models import Listing, RawPayload, SearchConfig
from src.providers.base import ListingProvider, ProviderError

DEFAULT_RENTCAST_LISTINGS_URL = "https://api.rentcast.io/v1/listings/sale"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_RETRY_BACKOFF_SECONDS = (0.25, 0.5)
DEFAULT_QUERY_LIMIT = "500"
RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
ZIP_CODE_PATTERN = re.compile(r"^\d{5}(?:-\d{4})?$")


class RentCastListingProvider(ListingProvider):
    """HTTP provider adapter for the RentCast sale listings API."""

    provider_name = "rentcast"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_RENTCAST_LISTINGS_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        retry_backoff_seconds: tuple[float, ...] = DEFAULT_RETRY_BACKOFF_SECONDS,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = _resolve_api_key(api_key)
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._retry_backoff_seconds = retry_backoff_seconds
        self._client = client
        self._sleep = sleep

    def fetch_listings(self, search_config: SearchConfig) -> list[Listing]:
        """Fetch and normalize RentCast sale listings for a single search."""

        payload = self._fetch_payload(search_config)
        raw_results = _extract_results(payload)

        return [
            _normalize_listing(raw_listing, search_config, self.provider_name)
            for raw_listing in raw_results
        ]

    def _fetch_payload(self, search_config: SearchConfig) -> list[dict[str, Any]] | dict[str, Any]:
        params = _build_query_params(search_config)
        headers = {
            "X-Api-Key": self._api_key,
            "Accept": "application/json",
        }

        try:
            response = self._get_with_retry(
                params=params,
                headers=headers,
            )
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "RentCast request timed out after "
                f"{self._timeout_seconds} seconds for search "
                f"'{search_config.search_name}' after "
                f"{_max_attempts(self._retry_backoff_seconds)} attempts."
            ) from exc
        except httpx.NetworkError as exc:
            raise ProviderError(
                f"RentCast request failed for search "
                f"'{search_config.search_name}' after "
                f"{_max_attempts(self._retry_backoff_seconds)} attempts."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                "RentCast request failed with status "
                f"{exc.response.status_code} for search "
                f"'{search_config.search_name}'{_attempt_suffix(exc.request)}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"RentCast request failed for search '{search_config.search_name}'."
            ) from exc
        except ValueError as exc:
            raise ProviderError(
                f"RentCast returned invalid JSON for search '{search_config.search_name}'."
            ) from exc

        if payload is None:
            return []

        if not isinstance(payload, list | dict):
            raise ProviderError("RentCast response must be a JSON array or object.")

        return payload

    def _get_with_retry(
        self,
        *,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> httpx.Response:
        for attempt_number in range(1, _max_attempts(self._retry_backoff_seconds) + 1):
            try:
                response = self._send_get(params=params, headers=headers)
                response.request.extensions["attempt_number"] = attempt_number
                response.raise_for_status()
                return response
            except httpx.TimeoutException:
                if not _has_retry_attempt_remaining(
                    attempt_number, self._retry_backoff_seconds
                ):
                    raise
            except httpx.NetworkError:
                if not _has_retry_attempt_remaining(
                    attempt_number, self._retry_backoff_seconds
                ):
                    raise
            except httpx.HTTPStatusError as exc:
                exc.request.extensions["attempt_number"] = attempt_number
                if not _should_retry_status_error(
                    exc, attempt_number, self._retry_backoff_seconds
                ):
                    raise

            self._sleep(_retry_delay(attempt_number, self._retry_backoff_seconds))

        raise AssertionError("Retry loop should return a response or raise an error.")

    def _send_get(
        self,
        *,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> httpx.Response:
        if self._client is not None:
            return self._client.get(
                self._base_url,
                params=params,
                headers=headers,
                timeout=self._timeout_seconds,
            )

        with httpx.Client() as client:
            return client.get(
                self._base_url,
                params=params,
                headers=headers,
                timeout=self._timeout_seconds,
            )


# Backward-compatible alias for existing imports while the repo transitions names.
SampleListingProvider = RentCastListingProvider


def _resolve_api_key(api_key: str | None) -> str:
    resolved_api_key = api_key or os.getenv("LISTING_PROVIDER_API_KEY", "").strip()
    if not resolved_api_key:
        raise ProviderError(
            "LISTING_PROVIDER_API_KEY environment variable is required for "
            "RentCastListingProvider."
        )
    return resolved_api_key


def _build_query_params(search_config: SearchConfig) -> dict[str, str]:
    params = {
        "limit": DEFAULT_QUERY_LIMIT,
        "suppressLogging": "true",
    }
    params.update(_location_query_params(search_config.location))
    return params


def _location_query_params(location: str) -> dict[str, str]:
    normalized_location = location.strip()
    if not normalized_location:
        raise ProviderError("Search location must be a non-empty string.")

    if ZIP_CODE_PATTERN.fullmatch(normalized_location):
        return {"zipCode": normalized_location}

    if "," in normalized_location:
        city_part, state_part = normalized_location.rsplit(",", maxsplit=1)
        city = city_part.strip()
        state = state_part.strip()
        if city and state:
            return {"city": city, "state": state}

    return {"city": normalized_location}


def _max_attempts(retry_backoff_seconds: tuple[float, ...]) -> int:
    return len(retry_backoff_seconds) + 1


def _retry_delay(
    attempt_number: int,
    retry_backoff_seconds: tuple[float, ...],
) -> float:
    return retry_backoff_seconds[attempt_number - 1]


def _has_retry_attempt_remaining(
    attempt_number: int,
    retry_backoff_seconds: tuple[float, ...],
) -> bool:
    return attempt_number < _max_attempts(retry_backoff_seconds)


def _should_retry_status_error(
    exc: httpx.HTTPStatusError,
    attempt_number: int,
    retry_backoff_seconds: tuple[float, ...],
) -> bool:
    return (
        exc.response.status_code in RETRYABLE_STATUS_CODES
        and attempt_number < _max_attempts(retry_backoff_seconds)
    )


def _attempt_suffix(request: httpx.Request) -> str:
    attempt_number = request.extensions.get("attempt_number")
    if isinstance(attempt_number, int) and attempt_number > 1:
        return f" after {attempt_number} attempts."
    return "."


def _extract_results(payload: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        raw_results = payload
    else:
        raw_results = payload.get("results")
        if raw_results is None:
            return []

    if not isinstance(raw_results, list):
        raise ProviderError("RentCast response results must be a list.")

    normalized_results: list[dict[str, Any]] = []
    for raw_listing in raw_results:
        if not isinstance(raw_listing, dict):
            raise ProviderError("Each RentCast listing must be a JSON object.")
        normalized_results.append(raw_listing)

    return normalized_results


def _normalize_listing(
    raw_listing: RawPayload,
    search_config: SearchConfig,
    provider_name: str,
) -> Listing:
    listing_id = _require_listing_id(raw_listing)
    address = _require_string(raw_listing, "addressLine1", fallback_fields=("formattedAddress",))
    city = _require_string(raw_listing, "city")
    state = _require_string(raw_listing, "state")
    price = _require_int(raw_listing, "price")
    url = _require_string(raw_listing, "url", fallback_fields=("listingUrl",))

    return Listing(
        listing_id=listing_id,
        search_name=search_config.search_name,
        address=address,
        city=city,
        state=state,
        zip_code=_optional_string(raw_listing, "zipCode", fallback_fields=("zip_code",)),
        price=price,
        beds=_optional_number(raw_listing, "bedrooms", fallback_fields=("beds",)),
        baths=_optional_number(raw_listing, "bathrooms", fallback_fields=("baths",)),
        sqft=_optional_int(raw_listing, "squareFootage", fallback_fields=("sqft",)),
        property_type=_normalize_property_type(
            _optional_string(raw_listing, "propertyType", fallback_fields=("property_type",))
        ),
        hoa_monthly=_extract_hoa_fee(raw_listing),
        status=_normalize_token(
            _optional_string(raw_listing, "status", fallback_fields=("listingStatus",))
        ),
        url=url,
        description=_optional_string(raw_listing, "description", fallback_fields=("remarks",)),
        provider_name=provider_name,
        raw_payload=dict(raw_listing),
    )


def _require_listing_id(raw_listing: RawPayload) -> str:
    for field_name in ("id", "listingId"):
        value = raw_listing.get(field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, int):
            return str(value)

    raise ProviderError("RentCast listing must include a non-empty 'id' or 'listingId'.")


def _require_string(
    raw_listing: RawPayload,
    field_name: str,
    *,
    fallback_fields: tuple[str, ...] = (),
) -> str:
    value = _first_present_value(raw_listing, field_name, fallback_fields=fallback_fields)
    if not isinstance(value, str) or not value.strip():
        all_fields = ", ".join((field_name, *fallback_fields))
        raise ProviderError(
            f"RentCast listing field '{all_fields}' must contain a non-empty string."
        )
    return value.strip()


def _optional_string(
    raw_listing: RawPayload,
    field_name: str,
    *,
    fallback_fields: tuple[str, ...] = (),
) -> str | None:
    value = _first_present_value(raw_listing, field_name, fallback_fields=fallback_fields)
    if value is None:
        return None
    if not isinstance(value, str):
        all_fields = ", ".join((field_name, *fallback_fields))
        raise ProviderError(
            f"RentCast listing field '{all_fields}' must be a string when present."
        )

    normalized_value = value.strip()
    return normalized_value or None


def _require_int(
    raw_listing: RawPayload,
    field_name: str,
    *,
    fallback_fields: tuple[str, ...] = (),
) -> int:
    value = _first_present_value(raw_listing, field_name, fallback_fields=fallback_fields)
    resolved_int = _coerce_int(value)
    if resolved_int is None:
        all_fields = ", ".join((field_name, *fallback_fields))
        raise ProviderError(
            f"RentCast listing field '{all_fields}' must be an integer."
        )
    return resolved_int


def _optional_int(
    raw_listing: RawPayload,
    field_name: str,
    *,
    fallback_fields: tuple[str, ...] = (),
) -> int | None:
    value = _first_present_value(raw_listing, field_name, fallback_fields=fallback_fields)
    if value is None:
        return None

    resolved_int = _coerce_int(value)
    if resolved_int is None:
        all_fields = ", ".join((field_name, *fallback_fields))
        raise ProviderError(
            f"RentCast listing field '{all_fields}' must be an integer when present."
        )
    return resolved_int


def _optional_number(
    raw_listing: RawPayload,
    field_name: str,
    *,
    fallback_fields: tuple[str, ...] = (),
) -> float | None:
    value = _first_present_value(raw_listing, field_name, fallback_fields=fallback_fields)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        all_fields = ", ".join((field_name, *fallback_fields))
        raise ProviderError(
            f"RentCast listing field '{all_fields}' must be numeric when present."
        )
    return float(value)


def _extract_hoa_fee(raw_listing: RawPayload) -> int | None:
    hoa_value = raw_listing.get("hoa")
    if hoa_value is None:
        return _optional_int(raw_listing, "hoaFee", fallback_fields=("hoa_monthly",))

    if not isinstance(hoa_value, dict):
        raise ProviderError("RentCast listing field 'hoa' must be an object when present.")

    fee = hoa_value.get("fee")
    if fee is None:
        return None

    resolved_fee = _coerce_int(fee)
    if resolved_fee is None:
        raise ProviderError("RentCast listing field 'hoa.fee' must be an integer.")
    return resolved_fee


def _first_present_value(
    raw_listing: RawPayload,
    field_name: str,
    *,
    fallback_fields: tuple[str, ...],
) -> Any:
    for candidate_field in (field_name, *fallback_fields):
        if candidate_field in raw_listing:
            return raw_listing[candidate_field]
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _normalize_property_type(value: str | None) -> str | None:
    normalized_value = _normalize_token(value)
    if normalized_value is None:
        return None

    property_type_map = {
        "single_family": "single_family",
        "single_family_home": "single_family",
        "townhouse": "townhome",
        "townhome": "townhome",
        "condominium": "condo",
        "condo": "condo",
        "manufactured": "manufactured",
        "land": "land",
        "multi_family": "multi_family",
        "multifamily": "multi_family",
    }
    return property_type_map.get(normalized_value, normalized_value)


def _normalize_token(value: str | None) -> str | None:
    if value is None:
        return None

    normalized_value = value.strip().lower()
    if not normalized_value:
        return None

    return normalized_value.replace("-", "_").replace(" ", "_")
