"""Base interfaces and shared errors for listing providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.models import Listing, SearchConfig


class ProviderError(RuntimeError):
    """Raised when a provider fetch or response normalization fails."""


class ListingProvider(ABC):
    """Abstract interface for provider adapters.

    Provider adapters fetch remote listing data and normalize it into the
    internal :class:`src.models.Listing` model used throughout the application.
    """

    @abstractmethod
    def fetch_listings(self, search_config: SearchConfig) -> list[Listing]:
        """Return normalized listings for a single configured search."""
