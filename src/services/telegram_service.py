"""Telegram notification delivery and deterministic listing alert formatting."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Protocol, Sequence

import httpx

from src.models import Listing

DEFAULT_TELEGRAM_API_BASE_URL = "https://api.telegram.org"
DEFAULT_TIMEOUT_SECONDS = 10.0
TELEGRAM_MESSAGE_LIMIT = 4096
_PART_HEADER_RESERVE = " (Part 999/999)"


class TelegramError(RuntimeError):
    """Raised when Telegram configuration or delivery fails."""


class Notifier(ABC):
    """Abstract interface for outbound notification services."""

    @abstractmethod
    def send_message(self, message: str) -> None:
        """Send a plain-text notification message."""


class _SupportsPost(Protocol):
    def post(
        self,
        url: str,
        *,
        json: dict[str, object],
        timeout: float,
    ) -> httpx.Response:
        """Send an HTTP POST request."""


class TelegramNotifier(Notifier):
    """Notifier implementation backed by the Telegram Bot API."""

    def __init__(
        self,
        *,
        bot_token: str | None = None,
        chat_id: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        api_base_url: str = DEFAULT_TELEGRAM_API_BASE_URL,
        client: _SupportsPost | None = None,
    ) -> None:
        self._bot_token = _resolve_required_env(
            value=bot_token,
            env_name="TELEGRAM_BOT_TOKEN",
            service_name="TelegramNotifier",
        )
        self._chat_id = _resolve_required_env(
            value=chat_id,
            env_name="TELEGRAM_CHAT_ID",
            service_name="TelegramNotifier",
        )
        self._timeout_seconds = timeout_seconds
        self._send_message_url = (
            f"{api_base_url.rstrip('/')}/bot{self._bot_token}/sendMessage"
        )
        self._client = client

    def send_message(self, message: str) -> None:
        """Send a plain-text message, splitting it if needed for Telegram."""

        message_parts = split_message_for_telegram(
            message,
            max_message_length=TELEGRAM_MESSAGE_LIMIT,
        )

        if self._client is not None:
            for message_part in message_parts:
                self._send_single_message(self._client, message_part)
            return

        with httpx.Client() as client:
            for message_part in message_parts:
                self._send_single_message(client, message_part)

    def send_listing_alert(self, search_name: str, listings: Sequence[Listing]) -> None:
        """Format listings into deterministic Telegram messages and send them."""

        for message in format_listing_alert_messages(search_name, listings):
            self.send_message(message)

    def _send_single_message(
        self,
        client: _SupportsPost,
        message: str,
    ) -> None:
        payload = {
            "chat_id": self._chat_id,
            "text": message,
            "disable_web_page_preview": True,
        }

        try:
            response = client.post(
                self._send_message_url,
                json=payload,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise TelegramError(
                "Telegram sendMessage request timed out after "
                f"{self._timeout_seconds} seconds."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise TelegramError(
                "Telegram sendMessage request failed with status "
                f"{exc.response.status_code}."
            ) from exc
        except httpx.HTTPError as exc:
            raise TelegramError("Telegram sendMessage request failed.") from exc


def format_listing_alert_messages(
    search_name: str,
    listings: Sequence[Listing],
    *,
    max_message_length: int = TELEGRAM_MESSAGE_LIMIT,
) -> list[str]:
    """Return one or more plain-text Telegram messages for listing alerts."""

    normalized_search_name = search_name.strip() or "unnamed_search"
    summary_line = f"Found {len(listings)} new or changed listings."
    base_header_line = f"Real Estate Monitor: {normalized_search_name}"
    single_header = f"{base_header_line}\n{summary_line}"
    reserved_header = f"{base_header_line}{_PART_HEADER_RESERVE}\n{summary_line}"

    if len(single_header) > max_message_length:
        raise TelegramError("Telegram alert header exceeds the configured size limit.")

    if not listings:
        return [single_header]

    listing_blocks = [
        _format_listing_block(index=index, listing=listing)
        for index, listing in enumerate(listings, start=1)
    ]

    chunk_bodies = _chunk_listing_blocks(
        listing_blocks=listing_blocks,
        header_text=reserved_header,
        max_message_length=max_message_length,
    )

    if len(chunk_bodies) == 1:
        return [f"{single_header}\n\n{chunk_bodies[0]}"]

    total_parts = len(chunk_bodies)
    messages: list[str] = []
    for index, chunk_body in enumerate(chunk_bodies, start=1):
        part_header = (
            f"{base_header_line} (Part {index}/{total_parts})\n{summary_line}"
        )
        messages.append(f"{part_header}\n\n{chunk_body}")

    return messages


def split_message_for_telegram(
    message: str,
    *,
    max_message_length: int = TELEGRAM_MESSAGE_LIMIT,
) -> list[str]:
    """Split a message into Telegram-safe chunks without using Markdown."""

    if max_message_length <= 0:
        raise ValueError("max_message_length must be greater than zero.")

    normalized_message = message.strip()
    if not normalized_message:
        raise TelegramError("Telegram message cannot be empty.")

    if len(normalized_message) <= max_message_length:
        return [normalized_message]

    paragraphs = normalized_message.split("\n\n")
    return _chunk_segments(
        segments=paragraphs,
        separator="\n\n",
        max_length=max_message_length,
    )


def _chunk_listing_blocks(
    *,
    listing_blocks: Sequence[str],
    header_text: str,
    max_message_length: int,
) -> list[str]:
    available_body_length = max_message_length - len(header_text) - 2
    if available_body_length <= 0:
        raise TelegramError("Telegram alert header leaves no room for listing content.")

    return _chunk_segments(
        segments=listing_blocks,
        separator="\n\n",
        max_length=available_body_length,
    )


def _chunk_segments(
    *,
    segments: Sequence[str],
    separator: str,
    max_length: int,
) -> list[str]:
    chunks: list[str] = []
    current_chunk = ""

    for segment in segments:
        if not segment:
            continue

        normalized_segment = segment.strip()
        if len(normalized_segment) > max_length:
            smaller_segments = _split_oversized_segment(
                normalized_segment,
                max_length=max_length,
            )
        else:
            smaller_segments = [normalized_segment]

        for smaller_segment in smaller_segments:
            candidate = smaller_segment
            if current_chunk:
                candidate = f"{current_chunk}{separator}{smaller_segment}"

            if len(candidate) <= max_length:
                current_chunk = candidate
                continue

            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = smaller_segment

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _split_oversized_segment(segment: str, *, max_length: int) -> list[str]:
    line_chunks = _split_by_delimiter(segment, delimiter="\n", max_length=max_length)

    normalized_chunks: list[str] = []
    for chunk in line_chunks:
        if len(chunk) <= max_length:
            normalized_chunks.append(chunk)
            continue

        normalized_chunks.extend(
            _split_by_delimiter(chunk, delimiter=" ", max_length=max_length)
        )

    final_chunks: list[str] = []
    for chunk in normalized_chunks:
        if len(chunk) <= max_length:
            final_chunks.append(chunk)
            continue

        for start in range(0, len(chunk), max_length):
            final_chunks.append(chunk[start : start + max_length])

    return final_chunks


def _split_by_delimiter(text: str, *, delimiter: str, max_length: int) -> list[str]:
    parts = text.split(delimiter)
    chunks: list[str] = []
    current_chunk = ""

    for part in parts:
        candidate = part if not current_chunk else f"{current_chunk}{delimiter}{part}"
        if len(candidate) <= max_length:
            current_chunk = candidate
            continue

        if current_chunk:
            chunks.append(current_chunk)
        current_chunk = part

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _format_listing_block(*, index: int, listing: Listing) -> str:
    lines = [
        f"{index}) {_format_address_line(listing)}",
        f"Price: {_format_currency(listing.price)}",
    ]

    beds_and_baths = _format_beds_and_baths(listing)
    if beds_and_baths is not None:
        lines.append(f"Beds/Baths: {beds_and_baths}")

    if listing.sqft is not None:
        lines.append(f"Sq Ft: {listing.sqft:,}")

    if listing.property_type:
        lines.append(f"Property Type: {_humanize_token(listing.property_type)}")

    if listing.hoa_monthly is not None:
        lines.append(f"HOA: {_format_currency(listing.hoa_monthly)}/month")

    if listing.status:
        lines.append(f"Status: {_humanize_token(listing.status)}")

    lines.append(f"Link: {listing.url}")
    return "\n".join(lines)


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


def _resolve_required_env(
    *,
    value: str | None,
    env_name: str,
    service_name: str,
) -> str:
    resolved_value = value if value is not None else os.getenv(env_name, "")
    normalized_value = resolved_value.strip()
    if not normalized_value:
        raise TelegramError(
            f"{env_name} environment variable is required for {service_name}."
        )
    return normalized_value
