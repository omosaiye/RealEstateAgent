"""LLM-backed listing summarization with deterministic fallback formatting."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

import httpx

from src.models import Listing, SearchConfig

DEFAULT_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "listing_summary.txt"
DEFAULT_OPENAI_API_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_TIMEOUT_SECONDS = 15.0


class SummarizerError(RuntimeError):
    """Raised when prompt loading or LLM request setup fails."""


class ListingSummarizer(ABC):
    """Abstract interface for listing summary generation."""

    @abstractmethod
    def summarize(
        self,
        search_name: str,
        criteria: SearchConfig | Mapping[str, object],
        listings: Sequence[Listing],
    ) -> str:
        """Return a Telegram-friendly summary for matched listings."""


class _SupportsPost(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> httpx.Response:
        """Send an HTTP POST request."""


class OpenAISummarizer(ListingSummarizer):
    """Listing summarizer that calls the OpenAI Responses API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_OPENAI_MODEL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        api_base_url: str = DEFAULT_OPENAI_API_BASE_URL,
        prompt_path: str | Path = DEFAULT_PROMPT_PATH,
        client: _SupportsPost | None = None,
    ) -> None:
        self._api_key = _resolve_required_env(
            value=api_key,
            env_name="OPENAI_API_KEY",
            service_name="OpenAISummarizer",
        )
        self._model = model.strip()
        if not self._model:
            raise SummarizerError("OpenAISummarizer requires a non-empty model name.")

        normalized_base_url = api_base_url.strip().rstrip("/")
        if not normalized_base_url:
            raise SummarizerError("OpenAISummarizer requires a non-empty API base URL.")

        self._responses_url = f"{normalized_base_url}/responses"
        self._timeout_seconds = timeout_seconds
        self._prompt_template = load_prompt_template(prompt_path)
        self._client = client

    @property
    def prompt_template(self) -> str:
        """Return the loaded prompt template text."""

        return self._prompt_template

    def summarize(
        self,
        search_name: str,
        criteria: SearchConfig | Mapping[str, object],
        listings: Sequence[Listing],
    ) -> str:
        """Return an LLM summary, or deterministic fallback text on request failure."""

        if not listings:
            return _format_empty_summary(search_name)

        prompt_text = _render_prompt(
            prompt_template=self._prompt_template,
            search_name=search_name,
            criteria=criteria,
            listings=listings,
        )

        try:
            return self._request_summary(prompt_text)
        except SummarizerError:
            return format_summary_fallback(search_name, criteria, listings)

    def _request_summary(self, prompt_text: str) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "input": prompt_text,
            "max_output_tokens": 400,
        }

        if self._client is not None:
            return _post_summary_request(
                client=self._client,
                url=self._responses_url,
                headers=headers,
                payload=payload,
                timeout_seconds=self._timeout_seconds,
            )

        with httpx.Client() as client:
            return _post_summary_request(
                client=client,
                url=self._responses_url,
                headers=headers,
                payload=payload,
                timeout_seconds=self._timeout_seconds,
            )


def load_prompt_template(path: str | Path = DEFAULT_PROMPT_PATH) -> str:
    """Load and validate the summarization prompt template from disk."""

    prompt_path = Path(path)

    try:
        prompt_text = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SummarizerError(
            f"Unable to read summarization prompt template: {prompt_path}"
        ) from exc

    normalized_prompt = prompt_text.strip()
    if not normalized_prompt:
        raise SummarizerError(
            f"Summarization prompt template is empty: {prompt_path}"
        )

    return normalized_prompt


def format_summary_fallback(
    search_name: str,
    criteria: SearchConfig | Mapping[str, object],
    listings: Sequence[Listing],
) -> str:
    """Build a deterministic summary that does not depend on LLM availability."""

    normalized_search_name = search_name.strip() or "unnamed_search"
    header_lines = [
        f"Real Estate Monitor: {normalized_search_name}",
        f"Found {len(listings)} new or changed listings.",
    ]

    if not listings:
        return "\n".join(header_lines)

    criteria_values = _criteria_to_dict(criteria)
    listing_blocks = [
        _format_fallback_listing_block(
            index=index,
            criteria_values=criteria_values,
            listing=listing,
        )
        for index, listing in enumerate(listings, start=1)
    ]
    return "\n\n".join(["\n".join(header_lines), *listing_blocks])


def _post_summary_request(
    *,
    client: _SupportsPost,
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
    timeout_seconds: float,
) -> str:
    try:
        response = client.post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise SummarizerError(
            f"OpenAI summarization request timed out after {timeout_seconds} seconds."
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise SummarizerError(
            "OpenAI summarization request failed with status "
            f"{exc.response.status_code}."
        ) from exc
    except httpx.HTTPError as exc:
        raise SummarizerError("OpenAI summarization request failed.") from exc

    try:
        response_body = response.json()
    except ValueError as exc:
        raise SummarizerError("OpenAI summarization response was not valid JSON.") from exc

    summary_text = _extract_summary_text(response_body)
    if not summary_text:
        raise SummarizerError("OpenAI summarization response did not include summary text.")

    return summary_text


def _render_prompt(
    *,
    prompt_template: str,
    search_name: str,
    criteria: SearchConfig | Mapping[str, object],
    listings: Sequence[Listing],
) -> str:
    try:
        return prompt_template.format(
            search_name=search_name.strip(),
            criteria=_serialize_criteria(criteria),
            listing_json=_serialize_listings(listings),
        )
    except KeyError as exc:
        missing_name = exc.args[0]
        raise SummarizerError(
            f"Summarization prompt template is missing the '{missing_name}' placeholder."
        ) from exc


def _serialize_criteria(criteria: SearchConfig | Mapping[str, object]) -> str:
    return json.dumps(_criteria_to_prompt_dict(criteria), indent=2, sort_keys=True)


def _serialize_listings(listings: Sequence[Listing]) -> str:
    prompt_listings = [_listing_to_prompt_dict(listing) for listing in listings]
    return json.dumps(prompt_listings, indent=2, sort_keys=True)


def _criteria_to_dict(criteria: SearchConfig | Mapping[str, object]) -> dict[str, object]:
    if isinstance(criteria, SearchConfig):
        return asdict(criteria)

    if isinstance(criteria, Mapping):
        return dict(criteria)

    raise SummarizerError(
        "Summarizer criteria must be a SearchConfig or mapping of search values."
    )


def _criteria_to_prompt_dict(
    criteria: SearchConfig | Mapping[str, object],
) -> dict[str, object]:
    raw_criteria = _criteria_to_dict(criteria)
    prompt_fields = (
        "location",
        "max_price",
        "min_beds",
        "min_baths",
        "property_types",
        "max_hoa",
        "min_sqft",
        "keywords_include",
        "keywords_exclude",
    )
    return {
        field_name: raw_criteria[field_name]
        for field_name in prompt_fields
        if field_name in raw_criteria and raw_criteria[field_name] not in (None, [])
    }


def _listing_to_prompt_dict(listing: Listing) -> dict[str, object]:
    return {
        "listing_id": listing.listing_id,
        "address": listing.address,
        "city": listing.city,
        "state": listing.state,
        "zip_code": listing.zip_code,
        "price": listing.price,
        "beds": listing.beds,
        "baths": listing.baths,
        "sqft": listing.sqft,
        "property_type": listing.property_type,
        "hoa_monthly": listing.hoa_monthly,
        "status": listing.status,
        "url": listing.url,
        "description": listing.description,
        "provider_name": listing.provider_name,
    }


def _extract_summary_text(response_body: Any) -> str:
    if not isinstance(response_body, dict):
        return ""

    output_text = response_body.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output_items = response_body.get("output")
    if isinstance(output_items, list):
        extracted_parts: list[str] = []
        for item in output_items:
            if not isinstance(item, dict):
                continue
            content_items = item.get("content")
            if not isinstance(content_items, list):
                continue
            for content_item in content_items:
                if not isinstance(content_item, dict):
                    continue
                text = content_item.get("text")
                if isinstance(text, str) and text.strip():
                    extracted_parts.append(text.strip())

        if extracted_parts:
            return "\n".join(extracted_parts)

    choices = response_body.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()

    return ""


def _format_empty_summary(search_name: str) -> str:
    normalized_search_name = search_name.strip() or "unnamed_search"
    return (
        f"Real Estate Monitor: {normalized_search_name}\n"
        "Found 0 new or changed listings."
    )


def _format_fallback_listing_block(
    *,
    index: int,
    criteria_values: Mapping[str, object],
    listing: Listing,
) -> str:
    lines = [
        f"{index}) {_format_address_line(listing)}",
        f"Price: {_format_currency(listing.price)}",
    ]

    beds_and_baths = _format_beds_and_baths(listing)
    if beds_and_baths is not None:
        lines.append(f"Beds/Baths: {beds_and_baths}")

    match_reason = _build_match_reason(criteria_values, listing)
    lines.append(f"Why it matched: {match_reason}")
    lines.append(f"Link: {listing.url}")
    return "\n".join(lines)


def _build_match_reason(
    criteria_values: Mapping[str, object],
    listing: Listing,
) -> str:
    reasons: list[str] = []

    max_price = _as_int(criteria_values.get("max_price"))
    if max_price is not None:
        reasons.append(f"within the {_format_currency(max_price)} budget")

    min_beds = _as_float(criteria_values.get("min_beds"))
    if min_beds is not None and listing.beds is not None:
        reasons.append(f"meets the {_format_number(min_beds)}+ bed target")

    min_baths = _as_float(criteria_values.get("min_baths"))
    if min_baths is not None and listing.baths is not None:
        reasons.append(f"meets the {_format_number(min_baths)}+ bath target")

    property_types = criteria_values.get("property_types")
    if isinstance(property_types, list) and listing.property_type:
        normalized_types = {
            property_type.strip().lower()
            for property_type in property_types
            if isinstance(property_type, str) and property_type.strip()
        }
        if listing.property_type.strip().lower() in normalized_types:
            reasons.append(
                f"matches the {_humanize_token(listing.property_type)} property type"
            )

    min_sqft = _as_int(criteria_values.get("min_sqft"))
    if min_sqft is not None and listing.sqft is not None:
        reasons.append(f"offers {listing.sqft:,} square feet")

    max_hoa = _as_int(criteria_values.get("max_hoa"))
    if max_hoa is not None and listing.hoa_monthly is not None:
        reasons.append(f"has HOA dues of {_format_currency(listing.hoa_monthly)}/month")

    keyword_matches = _matching_keywords(criteria_values.get("keywords_include"), listing)
    if keyword_matches:
        reasons.append(f"mentions {', '.join(keyword_matches)}")

    if not reasons:
        return "matches the configured search filters."

    selected_reasons = reasons[:4]
    if len(selected_reasons) == 1:
        return f"{selected_reasons[0]}."

    prefix = ", ".join(selected_reasons[:-1])
    return f"{prefix}, and {selected_reasons[-1]}."


def _matching_keywords(criteria_keywords: object, listing: Listing) -> list[str]:
    if not isinstance(criteria_keywords, list):
        return []

    haystack = " ".join(
        filter(
            None,
            [
                listing.address.lower(),
                listing.description.lower() if listing.description else "",
            ],
        )
    )

    matches: list[str] = []
    for keyword in criteria_keywords:
        if not isinstance(keyword, str):
            continue

        normalized_keyword = keyword.strip().lower()
        if normalized_keyword and normalized_keyword in haystack:
            matches.append(normalized_keyword)

    return matches[:2]


def _format_address_line(listing: Listing) -> str:
    locality_parts = [listing.city.strip(), listing.state.strip()]
    if listing.zip_code:
        locality_parts.append(listing.zip_code.strip())

    locality = ", ".join(part for part in locality_parts[:2] if part)
    if len(locality_parts) == 3:
        locality = f"{locality} {locality_parts[2]}".strip()

    if locality:
        return f"{listing.address}, {locality}"
    return listing.address


def _format_beds_and_baths(listing: Listing) -> str | None:
    if listing.beds is None and listing.baths is None:
        return None

    beds_text = _format_number(listing.beds) if listing.beds is not None else "n/a"
    baths_text = _format_number(listing.baths) if listing.baths is not None else "n/a"
    return f"{beds_text}/{baths_text}"


def _format_currency(value: int) -> str:
    return f"${value:,}"


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"


def _humanize_token(value: str) -> str:
    return value.strip().replace("_", " ")


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _as_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _resolve_required_env(
    *,
    value: str | None,
    env_name: str,
    service_name: str,
) -> str:
    resolved_value = value if value is not None else os.getenv(env_name, "")
    normalized_value = resolved_value.strip()
    if not normalized_value:
        raise SummarizerError(
            f"{env_name} environment variable is required for {service_name}."
        )
    return normalized_value
