from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

import requests

from apartment_search.models import Listing


OPEN_HPD_VIOLATIONS_ENDPOINT = "https://data.cityofnewyork.us/resource/csn4-vhvf.json"


@dataclass(slots=True)
class HpdRiskSummary:
    checked: bool
    open_violation_count: int = 0
    class_counts: dict[str, int] | None = None
    sample_violations: list[str] | None = None
    error: str | None = None

    @property
    def risk_label(self) -> str:
        if not self.checked:
            return "not_checked"
        if self.error:
            return "unknown"
        if self.open_violation_count >= 20:
            return "high"
        if self.open_violation_count >= 5:
            return "medium"
        if self.open_violation_count > 0:
            return "low"
        return "clear"

    def as_dict(self) -> dict[str, Any]:
        return {
            "checked": self.checked,
            "risk_label": self.risk_label,
            "open_violation_count": self.open_violation_count,
            "class_counts": self.class_counts or {},
            "sample_violations": self.sample_violations or [],
            "error": self.error,
        }


class HpdViolationClient:
    def __init__(
        self,
        enabled: bool | None = None,
        app_token: str | None = None,
        timeout_seconds: int = 20,
    ) -> None:
        self.enabled = enabled if enabled is not None else os.getenv("ENABLE_HPD_LOOKUP", "").lower() == "true"
        self.app_token = app_token or os.getenv("NYC_OPEN_DATA_APP_TOKEN")
        self.timeout_seconds = timeout_seconds

    def summarize_listing(self, listing: Listing) -> HpdRiskSummary:
        if not self.enabled:
            return HpdRiskSummary(checked=False)
        parsed = parse_nyc_address(listing.address or "")
        if not parsed:
            return HpdRiskSummary(checked=True, error="Could not parse listing address for HPD lookup.")

        house_number, street_name = parsed
        params = {
            "$limit": 50,
            "$where": f"upper(streetname)='{street_name.upper()}' AND housenumber='{house_number}'",
        }
        if listing.borough:
            params["boro"] = listing.borough.upper()
        headers = {"X-App-Token": self.app_token} if self.app_token else {}

        try:
            response = requests.get(
                OPEN_HPD_VIOLATIONS_ENDPOINT,
                params=params,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            records = response.json()
        except (requests.RequestException, ValueError) as exc:
            return HpdRiskSummary(checked=True, error=str(exc))

        if not isinstance(records, list):
            return HpdRiskSummary(checked=True, error="Unexpected HPD response shape.")

        class_counts = Counter(str(record.get("class", "unknown")) for record in records if isinstance(record, dict))
        samples = [
            str(record.get("novdescription") or record.get("violationdescription") or record.get("inspectiondate") or "")
            for record in records[:5]
            if isinstance(record, dict)
        ]
        return HpdRiskSummary(
            checked=True,
            open_violation_count=len(records),
            class_counts=dict(class_counts),
            sample_violations=[sample for sample in samples if sample],
        )


def parse_nyc_address(address: str) -> tuple[str, str] | None:
    match = re.match(r"^\s*([0-9]+[A-Za-z-]?)\s+(.+?)\s*$", address)
    if not match:
        return None
    house_number = match.group(1).upper()
    street_name = _normalize_street(match.group(2))
    return house_number, street_name


def _normalize_street(street_name: str) -> str:
    street = re.sub(r"\b(APT|UNIT|#)\b.*$", "", street_name, flags=re.IGNORECASE).strip()
    replacements = {
        r"\bST\b\.?": "STREET",
        r"\bAVE\b\.?": "AVENUE",
        r"\bAV\b\.?": "AVENUE",
        r"\bRD\b\.?": "ROAD",
        r"\bBLVD\b\.?": "BOULEVARD",
        r"\bPL\b\.?": "PLACE",
    }
    for pattern, replacement in replacements.items():
        street = re.sub(pattern, replacement, street, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", street).upper()
