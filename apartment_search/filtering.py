from __future__ import annotations

from apartment_search.models import FilterResult, LaundryStatus, Listing, PreferenceProfile


def filter_listing(listing: Listing, profile: PreferenceProfile) -> FilterResult:
    reasons: list[str] = []
    warnings: list[str] = []

    if listing.bedrooms is None:
        warnings.append("Bedroom count missing.")
    elif listing.bedrooms < profile.min_bedrooms:
        reasons.append(f"Below minimum bedroom count: {listing.bedrooms}.")

    if listing.bathrooms is None:
        warnings.append("Bathroom count missing.")
    elif listing.bathrooms < profile.min_bathrooms:
        reasons.append(f"Below minimum bathroom count: {listing.bathrooms}.")

    if listing.rent is None:
        warnings.append("Rent missing.")
    elif listing.rent > profile.budget.stretch_total_max:
        reasons.append(f"Rent ${listing.rent:,} exceeds stretch ceiling ${profile.budget.stretch_total_max:,}.")

    laundry_status = classify_laundry(listing)
    if laundry_status not in profile.acceptable_laundry:
        if laundry_status == LaundryStatus.UNKNOWN:
            reasons.append("Laundry status is unknown; laundry is a deal-breaker.")
        elif laundry_status == LaundryStatus.NEARBY:
            reasons.append("Nearby laundromat does not satisfy the laundry requirement.")
        else:
            reasons.append("No acceptable in-unit or in-building laundry signal.")

    if listing.commute_minutes is not None and listing.commute_minutes > profile.commute.max_minutes:
        reasons.append(
            f"Commute estimate {listing.commute_minutes} minutes exceeds max {profile.commute.max_minutes} minutes."
        )

    if listing.subway_walk_minutes is not None and listing.subway_walk_minutes > profile.commute.max_subway_walk_minutes:
        warnings.append(
            f"Subway walk estimate {listing.subway_walk_minutes} minutes is longer than preferred "
            f"{profile.commute.max_subway_walk_minutes} minutes."
        )

    return FilterResult(
        passes=not reasons,
        reasons=reasons,
        warnings=warnings,
        laundry_status=laundry_status,
    )


def classify_laundry(listing: Listing) -> LaundryStatus:
    if isinstance(listing.laundry_status, LaundryStatus) and listing.laundry_status != LaundryStatus.UNKNOWN:
        return listing.laundry_status
    if listing.laundry_status:
        try:
            status = LaundryStatus(str(listing.laundry_status))
        except ValueError:
            status = LaundryStatus.UNKNOWN
        if status != LaundryStatus.UNKNOWN:
            return status

    raw_status = listing.raw.get("laundry_status") if isinstance(listing.raw, dict) else None
    if raw_status:
        try:
            status = LaundryStatus(str(raw_status))
        except ValueError:
            status = LaundryStatus.UNKNOWN
        if status != LaundryStatus.UNKNOWN:
            return status

    amenity_tokens = {_normalize_token(amenity) for amenity in listing.amenities}
    if amenity_tokens & {"washer_dryer", "washerdryer", "in_unit_laundry", "in_unit_washer_dryer", "washer_dryer_in_unit"}:
        return LaundryStatus.IN_UNIT
    if amenity_tokens & {"laundry", "laundry_room", "in_building_laundry", "laundry_in_building", "building_laundry"}:
        return LaundryStatus.IN_BUILDING
    if amenity_tokens & {"nearby_laundromat", "laundromat_nearby", "laundry_nearby"}:
        return LaundryStatus.NEARBY
    if amenity_tokens & {"no_laundry", "laundry_not_available"}:
        return LaundryStatus.NONE
    return LaundryStatus.UNKNOWN


def _normalize_token(value: object) -> str:
    return str(value).strip().lower().replace("-", "_").replace("/", "_").replace(" ", "_")
