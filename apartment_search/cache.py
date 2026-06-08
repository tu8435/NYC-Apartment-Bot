from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from apartment_search.models import LaundryStatus, Listing


class ListingCache:
    """Persistent cache for enriched listing records already seen in prior runs."""

    def __init__(self, path: str | Path = "cache/apartment_search/listings.json") -> None:
        self.path = Path(path)
        self._data: dict[str, dict[str, Any]] | None = None
        self.hits = 0
        self.misses = 0

    def get(self, listing: Listing) -> Listing | None:
        key = listing_identity_key(listing)
        cached = self._load().get(key)
        if not cached:
            self.misses += 1
            return None
        self.hits += 1
        cached_listing = listing_from_dict(cached)
        return merge_listing_data(listing, cached_listing)

    def set(self, listing: Listing) -> None:
        key = listing_identity_key(listing)
        data = self._load()
        data[key] = listing_to_dict(listing)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def stats(self) -> dict[str, int]:
        return {
            "cached_listing_hits": self.hits,
            "cached_listing_misses": self.misses,
            "cached_listing_count": len(self._load()),
        }

    def _load(self) -> dict[str, dict[str, Any]]:
        if self._data is None:
            if self.path.exists():
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            else:
                self._data = {}
        return self._data


def listing_identity_key(listing: Listing) -> str:
    return listing.url or f"{listing.source}:{listing.source_id}"


def listing_to_dict(listing: Listing) -> dict[str, Any]:
    return asdict(listing)


def listing_from_dict(data: dict[str, Any]) -> Listing:
    allowed = Listing.__dataclass_fields__.keys()
    values = {key: value for key, value in data.items() if key in allowed}
    if "laundry_status" in values:
        values["laundry_status"] = _laundry_status(values["laundry_status"])
    return Listing(**values)


def _laundry_status(value: Any) -> LaundryStatus:
    if isinstance(value, LaundryStatus):
        return value
    try:
        return LaundryStatus(str(value))
    except ValueError:
        return LaundryStatus.UNKNOWN


def merge_listing_data(search_listing: Listing, cached_listing: Listing) -> Listing:
    for field_name in search_listing.__dataclass_fields__:
        search_value = getattr(search_listing, field_name)
        cached_value = getattr(cached_listing, field_name)
        if field_name == "raw":
            merged_raw = dict(cached_value or {})
            merged_raw.update(search_value or {})
            setattr(cached_listing, field_name, merged_raw)
        elif search_value not in (None, "", [], {}):
            setattr(cached_listing, field_name, search_value)
    return cached_listing
