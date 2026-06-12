# =========================
# APP/API/INTERNAL.PY
# =========================
"""
Internal utility endpoints (kein Domain-spezifischer Router).

Endpoints:
- GET /api/address-autocomplete — OpenStreetMap-Nominatim-Proxy

Extraktion aus app/main.py (siehe docs/react_handoff.md §6 — M0-Block).
Verhalten 1:1 erhalten; nur Modul-Ort + Router-Pattern geändert.
"""

from __future__ import annotations

import json
import logging
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["internal"])


def format_nominatim_result(item: dict) -> dict:
    """Format a single Nominatim search hit into our address-autocomplete shape."""
    address = item.get("address") or {}
    road = address.get("road") or address.get("pedestrian") or address.get("path") or ""
    house_number = address.get("house_number") or ""
    street = " ".join(part for part in [road, house_number] if part).strip()
    if not street:
        street = address.get("street") or ""
    postal_code = address.get("postcode") or ""
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("county")
        or ""
    )
    country_code = (address.get("country_code") or "").upper()
    country = address.get("country") or country_code
    label = item.get("display_name") or ", ".join(
        part for part in [street, f"{postal_code} {city}".strip(), country] if part
    )
    return {
        "label": label,
        "street": street,
        "zip": postal_code,
        "city": city,
        "country": country,
    }


@router.get("/address-autocomplete")
def address_autocomplete(q: str = "", country: str = "DE"):
    query = (q or "").strip()
    if len(query) < 3:
        return []

    params = {
        "q": query,
        "format": "json",
        "addressdetails": 1,
        "limit": 6,
    }
    if country:
        params["countrycodes"] = country.lower()
    url = f"https://nominatim.openstreetmap.org/search?{urlencode(params)}"
    request = UrlRequest(
        url,
        headers={
            "User-Agent": "FixundFertig/1.0 (autocomplete)",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []

    if not isinstance(payload, list):
        return []
    return [format_nominatim_result(item) for item in payload]
