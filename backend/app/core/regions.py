"""Country profiles for the markets we serve (United States and United Kingdom).

A tenant's ``country_code`` drives defaults (currency, units, time zone, date format) and address rules.
Its ``data_region`` records which regional deployment stores its data (``us`` or ``uk``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domains.projects.constants import US_STATES


@dataclass(frozen=True)
class CountryProfile:
    code: str
    name: str
    currency: str
    measurement_system: str
    timezone: str
    locale: str
    postal_label: str
    region_label: str | None  # "State" (US); UK addresses use a free-text county instead


COUNTRIES: dict[str, CountryProfile] = {
    "US": CountryProfile(
        "US", "United States", "USD", "us_customary", "America/New_York", "en-US", "ZIP code", "State"
    ),
    "GB": CountryProfile("GB", "United Kingdom", "GBP", "metric", "Europe/London", "en-GB", "Postcode", None),
}
MEASUREMENT_SYSTEMS = {"us_customary": "US customary (ft, yd, lb)", "metric": "Metric (m, m², m³, kg)"}

_US_ZIP = re.compile(r"^\d{5}(-\d{4})?$")
_UK_POSTCODE = re.compile(r"^([A-Z]{1,2}\d[A-Z\d]?) ?(\d[A-Z]{2})$")


def profile(country_code: str) -> CountryProfile:
    try:
        return COUNTRIES[country_code]
    except KeyError as exc:
        raise ValueError(f"Unsupported country; expected one of {sorted(COUNTRIES)}") from exc


def normalise_postal_code(country_code: str, value: str | None) -> str | None:
    """Validate and normalise a postal code for the country. Raises ValueError when invalid."""
    if value is None or value.strip() == "":
        return None
    raw = value.strip().upper()
    if country_code == "US":
        if not _US_ZIP.match(raw):
            raise ValueError("Use a 5-digit or ZIP+4 code")
        return raw
    if country_code == "GB":
        m = _UK_POSTCODE.match(re.sub(r"\s+", " ", raw))
        if not m:
            raise ValueError("Enter a valid UK postcode, e.g. SW1A 1AA")
        return f"{m.group(1)} {m.group(2)}"
    return raw


def validate_region(country_code: str, state_code: str | None) -> str | None:
    if state_code is None or state_code.strip() == "":
        return None
    code = state_code.strip().upper()
    if country_code == "US":
        if code not in US_STATES:
            raise ValueError("Unknown US state or territory code")
        return code
    raise ValueError("State is only used for US addresses; use county for UK addresses")
