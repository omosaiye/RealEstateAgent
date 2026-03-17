import httpx

from src.models import Listing, SearchConfig
from src.services.summarize_service import (
    OpenAISummarizer,
    format_summary_fallback,
    load_prompt_template,
)


class SpyLLMClient:
    def __init__(
        self,
        *,
        status_code: int = 200,
        response_json: dict[str, object] | None = None,
    ) -> None:
        self.status_code = status_code
        self.response_json = response_json or {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Triangle Homes\n1) 123 Main St is a strong fit.",
                        }
                    ]
                }
            ]
        }
        self.calls: list[dict[str, object]] = []

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> httpx.Response:
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        request = httpx.Request("POST", url, headers=headers)
        return httpx.Response(
            self.status_code,
            json=self.response_json,
            request=request,
        )


def build_search_config(**overrides: object) -> SearchConfig:
    search = SearchConfig(
        search_name="triangle_homes",
        enabled=True,
        location="Durham, NC",
        max_price=425000,
        min_beds=3.0,
        min_baths=2.0,
        property_types=["single_family", "townhome"],
        max_hoa=200,
        min_sqft=1600,
        keywords_include=["garage", "yard"],
    )
    for field_name, value in overrides.items():
        setattr(search, field_name, value)
    return search


def build_listing(**overrides: object) -> Listing:
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
        description="Updated kitchen with garage parking and fenced yard.",
        provider_name="sample_provider",
        raw_payload={"id": "listing-123"},
    )
    for field_name, value in overrides.items():
        setattr(listing, field_name, value)
    return listing


def test_load_prompt_template_reads_default_prompt_file() -> None:
    prompt_template = load_prompt_template()

    assert "Search name: {search_name}" in prompt_template
    assert "User criteria: {criteria}" in prompt_template
    assert "Listings:" in prompt_template
    assert "{listing_json}" in prompt_template


def test_openai_summarizer_returns_mocked_llm_summary_and_sends_expected_payload() -> None:
    client = SpyLLMClient()
    summarizer = OpenAISummarizer(
        api_key="openai-key-123",
        model="gpt-test-mini",
        client=client,
    )

    summary = summarizer.summarize(
        "triangle_homes",
        build_search_config(),
        [build_listing()],
    )

    assert summary == "Triangle Homes\n1) 123 Main St is a strong fit."
    assert client.calls == [
        {
            "url": "https://api.openai.com/v1/responses",
            "headers": {
                "Authorization": "Bearer openai-key-123",
                "Content-Type": "application/json",
            },
            "json": {
                "model": "gpt-test-mini",
                "input": client.calls[0]["json"]["input"],
                "max_output_tokens": 400,
            },
            "timeout": 15.0,
        }
    ]
    rendered_prompt = client.calls[0]["json"]["input"]
    assert isinstance(rendered_prompt, str)
    assert '"search_name": "triangle_homes"' not in rendered_prompt
    assert "Search name: triangle_homes" in rendered_prompt
    assert '"address": "123 Main St"' in rendered_prompt
    assert '"max_price": 425000' in rendered_prompt


def test_openai_summarizer_falls_back_to_deterministic_summary_on_llm_failure() -> None:
    client = SpyLLMClient(status_code=500, response_json={"error": "server_error"})
    summarizer = OpenAISummarizer(
        api_key="openai-key-123",
        client=client,
    )

    summary = summarizer.summarize(
        "triangle_homes",
        build_search_config(),
        [build_listing()],
    )

    assert summary == format_summary_fallback(
        "triangle_homes",
        build_search_config(),
        [build_listing()],
    )
    assert "Real Estate Monitor: triangle_homes" in summary
    assert "Found 1 new or changed listings." in summary
    assert "Why it matched: within the $425,000 budget" in summary
    assert "matches the single family property type" in summary
    assert "Link: https://example.com/listings/listing-123" in summary
