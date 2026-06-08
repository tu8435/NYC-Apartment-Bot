from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import requests

from apartment_search.models import Listing, PreferenceProfile


class CommuteEstimator:
    def __init__(self, api_key: str | None = None, timeout_seconds: int = 20) -> None:
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY")
        self.timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.api_key) and self.api_key.strip().lower() not in {"demo", "disabled", "none"}

    def enrich(self, listing: Listing, profile: PreferenceProfile) -> Listing:
        if self.api_key and self.api_key.strip().lower() == "demo":
            listing.raw["commute_mode"] = "google_maps_demo_no_external_request"
            listing.raw["commute_estimate_settings"] = commute_settings(profile)
            return listing
        if not self.enabled or (listing.commute_to_work_minutes is not None and listing.commute_home_minutes is not None):
            return listing
        origin = self._origin(listing)
        if not origin:
            return listing

        to_work = self._estimate_minutes(
            origin=origin,
            destination=profile.commute.destination_address,
            departure_time=next_weekday_timestamp(hour=9),
        )
        home = self._estimate_minutes(
            origin=profile.commute.destination_address,
            destination=origin,
            departure_time=next_weekday_timestamp(hour=18),
        )
        listing.commute_to_work_minutes = to_work
        listing.commute_home_minutes = home
        listing.commute_minutes = to_work
        listing.raw["commute_estimate_settings"] = commute_settings(profile)
        return listing

    def _estimate_minutes(self, origin: str, destination: str, departure_time: int) -> int | None:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/distancematrix/json",
            params={
                "origins": origin,
                "destinations": destination,
                "mode": "transit",
                "departure_time": departure_time,
                "key": self.api_key,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return _duration_minutes(response.json())

    def check_connection(self) -> dict[str, Any]:
        if not self.api_key:
            return {"configured": False, "ok": False, "mode": "missing", "error": "GOOGLE_MAPS_API_KEY is not set."}
        if self.api_key.strip().lower() == "demo":
            return {"configured": True, "ok": False, "mode": "demo", "error": "GOOGLE_MAPS_API_KEY is set to demo, so no live Maps request was made."}
        if not self.enabled:
            return {"configured": True, "ok": False, "mode": "disabled", "error": "GOOGLE_MAPS_API_KEY is disabled."}
        try:
            response = requests.get(
                "https://maps.googleapis.com/maps/api/distancematrix/json",
                params={
                    "origins": "163 Eldridge Street, New York, NY",
                    "destinations": "City Hall Park, New York, NY",
                    "mode": "transit",
                    "departure_time": next_weekday_timestamp(hour=9),
                    "key": self.api_key,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            return {"configured": True, "ok": False, "mode": "live", "error": str(exc)}

        status = payload.get("status")
        if status != "OK":
            return {
                "configured": True,
                "ok": False,
                "mode": "live",
                "status": status,
                "error": payload.get("error_message", "Google Maps returned a non-OK status."),
            }
        return {
            "configured": True,
            "ok": _duration_minutes(payload) is not None,
            "mode": "live",
            "status": status,
            "sample_minutes": _duration_minutes(payload),
        }

    @staticmethod
    def _origin(listing: Listing) -> str | None:
        if listing.latitude is not None and listing.longitude is not None:
            return f"{listing.latitude},{listing.longitude}"
        if listing.address:
            location = ", ".join(part for part in [listing.address, listing.neighborhood, listing.borough, "NY"] if part)
            return location
        return None


def _duration_minutes(payload: dict[str, Any]) -> int | None:
    rows = payload.get("rows", [])
    if not rows:
        return None
    elements = rows[0].get("elements", [])
    if not elements:
        return None
    duration = elements[0].get("duration") or elements[0].get("duration_in_traffic")
    if not duration:
        return None
    seconds = duration.get("value")
    if seconds is None:
        return None
    return round(seconds / 60)


def commute_settings(profile: PreferenceProfile) -> dict[str, Any]:
    return {
        "destination": profile.commute.destination_address,
        "to_work": "next weekday 09:00 America/New_York, apartment to work",
        "home": "next weekday 18:00 America/New_York, work to apartment",
    }


def next_weekday_timestamp(hour: int, timezone_name: str = "America/New_York") -> int:
    tz = ZoneInfo(timezone_name)
    now = datetime.now(tz)
    candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return int(candidate.timestamp())
