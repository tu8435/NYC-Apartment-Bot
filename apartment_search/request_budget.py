from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(slots=True)
class RequestBudgetEstimate:
    listings_considered: int
    expected_seen_cache_hits: int
    expected_unseen_listings: int
    rapidapi_search_requests: int
    rapidapi_detail_requests: int
    rapidapi_total_requests: int
    gemini_model_requests: int
    google_maps_requests: int
    hpd_requests: int

    def as_dict(self) -> dict[str, int]:
        return {
            "listings_considered": self.listings_considered,
            "expected_seen_cache_hits": self.expected_seen_cache_hits,
            "expected_unseen_listings": self.expected_unseen_listings,
            "rapidapi_search_requests": self.rapidapi_search_requests,
            "rapidapi_detail_requests": self.rapidapi_detail_requests,
            "rapidapi_total_requests": self.rapidapi_total_requests,
            "gemini_model_requests": self.gemini_model_requests,
            "google_maps_requests": self.google_maps_requests,
            "hpd_requests": self.hpd_requests,
        }


def estimate_requests(
    listings_considered: int = 100,
    per_page: int = 100,
    seen_cache_hit_rate: float = 0.0,
    detail_requests_needed: bool = False,
    use_gemini: bool = True,
    use_google_maps: bool = False,
    use_hpd: bool = False,
) -> RequestBudgetEstimate:
    cache_hits = round(listings_considered * max(0, min(1, seen_cache_hit_rate)))
    unseen = max(0, listings_considered - cache_hits)
    search_requests = max(1, math.ceil(listings_considered / max(per_page, 1)))
    detail_requests = unseen if detail_requests_needed else 0
    return RequestBudgetEstimate(
        listings_considered=listings_considered,
        expected_seen_cache_hits=cache_hits,
        expected_unseen_listings=unseen,
        rapidapi_search_requests=search_requests,
        rapidapi_detail_requests=detail_requests,
        rapidapi_total_requests=search_requests + detail_requests,
        gemini_model_requests=unseen if use_gemini else 0,
        google_maps_requests=unseen * 2 if use_google_maps else 0,
        hpd_requests=unseen if use_hpd else 0,
    )
