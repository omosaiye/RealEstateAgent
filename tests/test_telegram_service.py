import httpx
import pytest

from src.models import Listing
from src.services.telegram_service import (
    TelegramError,
    TelegramNotifier,
    format_listing_alert_messages,
)


class SpyTelegramClient:
    def __init__(self, *, status_code: int = 200) -> None:
        self.status_code = status_code
        self.calls: list[dict[str, object]] = []

    def post(
        self,
        url: str,
        *,
        json: dict[str, object],
        timeout: float,
    ) -> httpx.Response:
        self.calls.append(
            {
                "url": url,
                "json": json,
                "timeout": timeout,
            }
        )
        request = httpx.Request("POST", url)
        return httpx.Response(
            self.status_code,
            json={"ok": self.status_code == 200},
            request=request,
        )


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
        description="Updated kitchen and fenced yard.",
        provider_name="sample_provider",
        raw_payload={"id": "listing-123"},
    )
    for field_name, value in overrides.items():
        setattr(listing, field_name, value)
    return listing


def test_format_listing_alert_messages_formats_multiple_listings_in_plain_text() -> None:
    listings = [
        build_listing(),
        build_listing(
            listing_id="listing-456",
            address="456 Oak Ave",
            city="Raleigh",
            zip_code=None,
            price=425000,
            beds=4.0,
            baths=3.0,
            sqft=None,
            property_type="townhome",
            hoa_monthly=None,
            status=None,
            url="https://example.com/listings/listing-456",
            raw_payload={"id": "listing-456"},
        ),
    ]

    messages = format_listing_alert_messages("triangle_homes", listings)

    assert messages == [
        "\n".join(
            [
                "Real Estate Monitor: triangle_homes",
                "Found 2 new or changed listings.",
                "",
                "1) 123 Main St, Durham, NC 27701",
                "Price: $399,000",
                "Beds/Baths: 3/2.5",
                "Sq Ft: 1,800",
                "Property Type: single family",
                "HOA: $125/month",
                "Status: active",
                "Link: https://example.com/listings/listing-123",
                "",
                "2) 456 Oak Ave, Raleigh, NC",
                "Price: $425,000",
                "Beds/Baths: 4/3",
                "Property Type: townhome",
                "Link: https://example.com/listings/listing-456",
            ]
        )
    ]


def test_format_listing_alert_messages_splits_long_output_on_listing_boundaries() -> None:
    listings = [
        build_listing(),
        build_listing(
            listing_id="listing-456",
            address="456 Oak Ave",
            city="Raleigh",
            zip_code=None,
            price=425000,
            beds=4.0,
            baths=3.0,
            sqft=2100,
            property_type="townhome",
            hoa_monthly=210,
            status="coming_soon",
            url="https://example.com/listings/listing-456",
            raw_payload={"id": "listing-456"},
        ),
    ]

    messages = format_listing_alert_messages(
        "triangle_homes",
        listings,
        max_message_length=340,
    )

    assert len(messages) == 2
    assert "Real Estate Monitor: triangle_homes (Part 1/2)" in messages[0]
    assert "Real Estate Monitor: triangle_homes (Part 2/2)" in messages[1]
    assert "1) 123 Main St, Durham, NC 27701" in messages[0]
    assert "2) 456 Oak Ave, Raleigh, NC" in messages[1]
    assert all(len(message) <= 340 for message in messages)


def test_telegram_notifier_uses_env_credentials_and_sends_expected_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token-123")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat-id-456")
    client = SpyTelegramClient()
    notifier = TelegramNotifier(client=client, timeout_seconds=4.5)

    notifier.send_listing_alert("triangle_homes", [build_listing()])

    assert client.calls == [
        {
            "url": "https://api.telegram.org/botbot-token-123/sendMessage",
            "json": {
                "chat_id": "chat-id-456",
                "text": "\n".join(
                    [
                        "Real Estate Monitor: triangle_homes",
                        "Found 1 new or changed listings.",
                        "",
                        "1) 123 Main St, Durham, NC 27701",
                        "Price: $399,000",
                        "Beds/Baths: 3/2.5",
                        "Sq Ft: 1,800",
                        "Property Type: single family",
                        "HOA: $125/month",
                        "Status: active",
                        "Link: https://example.com/listings/listing-123",
                    ]
                ),
                "disable_web_page_preview": True,
            },
            "timeout": 4.5,
        }
    ]


def test_telegram_notifier_raises_clear_error_for_failed_send() -> None:
    client = SpyTelegramClient(status_code=500)
    notifier = TelegramNotifier(
        bot_token="bot-token-123",
        chat_id="chat-id-456",
        client=client,
    )

    with pytest.raises(
        TelegramError,
        match="Telegram sendMessage request failed with status 500.",
    ) as exc_info:
        notifier.send_message("Hello from the listing monitor.")

    assert "bot-token-123" not in str(exc_info.value)
    assert "chat-id-456" not in str(exc_info.value)
