"""
Property resolver: free-text address -> UPRN, coordinates, boundary polygon,
local authority code.

Sources:
  - OS Places API (DPA dataset)  -> UPRN, X/Y (BNG), LAT/LNG (WGS84)
  - planning.data.gov.uk /entity -> local-authority-district, boundary polygon (WKT)

NOTE ON VERIFICATION NEEDED (flagging honestly rather than guessing):
planning.data.gov.uk's spatial/point-based query parameters (e.g. searching
"which local-authority-district / boundary entity contains this point") were
not confirmed against live docs while writing this — the entity search
endpoint's documented params (q, typology, dataset, organisation_entity, entity,
curie, prefix, reference, period, start_date_year...) were captured from a
partial doc view. Confirm the exact parameter name for point-in-polygon /
longitude-latitude search against https://www.planning.data.gov.uk/docs before
trusting the boundary lookup below in production. The OS Places API call is
based on the current published technical spec and should be reliable as written.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import httpx

OS_PLACES_BASE_URL = "https://api.os.uk/search/places/v1/find"
PLANNING_DATA_BASE_URL = "https://www.planning.data.gov.uk/entity.json"


class PropertyNotFoundError(Exception):
    """Raised when the address cannot be resolved to a UPRN."""


class ResolverServiceError(Exception):
    """Raised on an unexpected upstream error (non-2xx, timeout, bad payload)."""


@dataclass
class ResolvedProperty:
    uprn: str
    address: str
    lat: float
    lon: float
    x_coordinate: float
    y_coordinate: float
    postcode: Optional[str]
    local_authority_code: Optional[str] = None
    polygon_wkt: Optional[str] = None


async def _call_os_places_find(address: str, api_key: str) -> dict:
    params = {"query": address, "key": api_key, "dataset": "DPA", "maxresults": 1}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(OS_PLACES_BASE_URL, params=params)
        except httpx.RequestError as exc:
            raise ResolverServiceError(f"OS Places API request failed: {exc}") from exc

    if resp.status_code == 404:
        raise PropertyNotFoundError(f"No match found for address: {address!r}")
    if resp.status_code != 200:
        raise ResolverServiceError(
            f"OS Places API returned HTTP {resp.status_code}: {resp.text[:200]}"
        )

    payload = resp.json()
    results = payload.get("results")
    if not results:
        raise PropertyNotFoundError(f"No match found for address: {address!r}")

    return results[0]["DPA"]


async def _lookup_local_authority(lat: float, lon: float) -> Optional[str]:
    """
    Look up the local-authority-district entity containing this point.

    See module docstring — the exact planning.data.gov.uk parameter for a
    point-based spatial query should be confirmed against live docs. Falls
    back to None (not a crash) if the lookup fails, per the roadmap's
    "resolver handles failure gracefully" success criterion.
    """
    params = {
        "dataset": "local-authority-district",
        "longitude": lon,
        "latitude": lat,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(PLANNING_DATA_BASE_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
            entities = payload.get("entities") or payload.get("results") or []
            if entities:
                return entities[0].get("reference") or entities[0].get("name")
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError, KeyError):
            return None
    return None


async def _lookup_boundary_polygon(uprn: str) -> Optional[str]:
    """Look up the boundary/parcel polygon (WKT) for a UPRN, where available."""
    params = {"dataset": "boundary", "q": uprn}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(PLANNING_DATA_BASE_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
            entities = payload.get("entities") or payload.get("results") or []
            if entities:
                return entities[0].get("geometry")
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError, KeyError):
            return None
    return None


async def resolve(address: str) -> ResolvedProperty:
    """
    Resolve a free-text UK property address to UPRN, coordinates, local
    authority code, and boundary polygon (where available).

    Raises PropertyNotFoundError if the address cannot be matched.
    Raises ResolverServiceError on unexpected upstream failure.
    Never raises on missing local_authority_code / polygon_wkt — those degrade
    to None rather than failing the whole resolution, since downstream agents
    can still operate on UPRN + coordinates alone.
    """
    api_key = os.environ.get("OS_PLACES_API_KEY")
    if not api_key:
        raise ResolverServiceError(
            "OS_PLACES_API_KEY not set. Add the OS Places API product to your "
            "OS Data Hub account and store the key as a Codespace secret."
        )

    dpa = await _call_os_places_find(address, api_key)

    uprn = dpa.get("UPRN")
    lat = dpa.get("LAT")
    lon = dpa.get("LNG")
    x_coord = dpa.get("X_COORDINATE")
    y_coord = dpa.get("Y_COORDINATE")
    postcode = dpa.get("POSTCODE")
    matched_address = dpa.get("ADDRESS", address)

    if uprn is None or lat is None or lon is None:
        raise ResolverServiceError(
            f"OS Places API returned an incomplete record for {address!r}: {dpa}"
        )

    local_authority_code = await _lookup_local_authority(lat, lon)
    polygon_wkt = await _lookup_boundary_polygon(uprn)

    return ResolvedProperty(
        uprn=str(uprn),
        address=matched_address,
        lat=float(lat),
        lon=float(lon),
        x_coordinate=float(x_coord) if x_coord is not None else None,
        y_coordinate=float(y_coord) if y_coord is not None else None,
        postcode=postcode,
        local_authority_code=local_authority_code,
        polygon_wkt=polygon_wkt,
    )
