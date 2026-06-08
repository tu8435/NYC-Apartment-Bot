from __future__ import annotations

from abc import ABC, abstractmethod

from apartment_search.models import Listing, PreferenceProfile


class ListingProvider(ABC):
    """Provider boundary for rental listing APIs."""

    @abstractmethod
    def search(self, profile: PreferenceProfile) -> list[Listing]:
        """Return normalized listings matching the broad search profile."""

    @abstractmethod
    def fetch_details(self, listing: Listing) -> Listing:
        """Return a listing enriched with detail-page fields."""

    def stats(self) -> dict[str, int]:
        """Return provider-side request counters."""
        return {}
