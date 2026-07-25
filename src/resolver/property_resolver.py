"""
Property resolver: free-text address -> UPRN, coordinates, local authority
code. Does NOT return a property boundary polygon — see VERIFICATION STATUS
below for why.

Sources:
  - OS Places API (DPA dataset)  -> UPRN, X/Y (BNG), LAT/LNG (WGS84), match score
  - planning.data.gov.uk /entity -> local-authority-district (point lookup)

MATCH CONFIDENCE (added 2026-07-25):
`ResolvedProperty.match_score` / `match_description` surface OS Places API's
own `MATCH` (0-1 float) and `MATCH_DESCRIPTION` fields. This matters because
`resolve()` always returns `results[0]` — the single best candidate — with no
guarantee it's the *right* one. Confirmed on a real call: searching
"14 Amhurst Road, London E8 1LL" returned UPRN 10008231087, "41, AMHURST ROAD,
LONDON, E8 1LL" — a different, real property on the same street and postcode,
NOT number 14 (which doesn't exist) — and OS Places still labelled it
MATCH_DESCRIPTION: "GOOD" (score 0.8). A "GOOD" description does not mean the
returned address is the same one that was asked for at the house-number
level. Callers (the CLI, the orchestrator, the eventual Gradio UI) must check
match_score/match_description themselves and decide whether to warn a user or
require confirmation on anything below a high-confidence threshold — this
resolver surfaces the signal but does not itself decide what counts as "close
enough".

VERIFICATION STATUS (checked against https://www.planning.data.gov.uk/docs, 2026-07-25):
- `entity.json?latitude=..&longitude=..&dataset=local-authority-district` IS the
  documented point-intersection query shape. `_lookup_local_authority` below is
  correct as written.
- There is no `boundary` dataset on planning.data.gov.uk, and no free/open
  source of a property's own parcel polygon generally (that's HMLR's licensed
  INSPIRE Index Polygons product). RESOLVED 2026-07-25 (see Architecture
  Decisions & Changes in CON29_ROADMAP_v2.md): the resolver no longer attempts
  to source a polygon. `polygon_wkt` is retained on `ResolvedProperty` as an
  always-None field for now. Sprint 1's `planning_agent.py` must query
  planning.data.gov.uk by point (lat/lon) intersection instead of assuming a
  pre-built property polygon — flagged there too, not yet built.
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
    match_score: Optional[float] = None
    match_description: Optional[str] = None
    local_authority_code: Optional[str] = None
    # Not sourced by this resolver — see Architecture Decisions & Changes,
    # 2026-07-25, in CON29_ROADMAP_v2.md. No free/open source of a property's
    # own parcel polygon exists (that's HMLR's licensed INSPIRE Index Polygons).
    # Downstream agents query planning.data.gov.uk by point (lat/lon) instead.
    # Kept as a field in case a licensed polygon source is added later.
    polygon_wkt: Optional[str] = None


async def _call_os_places_find(address: str, api_key: str) -> dict:
    # output_srs=WGS84 is required, not optional: OS Places API defaults to
    # EPSG:27700 (British National Grid, X/Y only) and omits LAT/LNG entirely
    # unless WGS84 output is explicitly requested. Without this, every real
    # call returns a DPA record with no LAT/LNG field, and resolve() below
    # would raise ResolverServiceError on every genuine address. Confirmed
    # against a real API response on 2026-07-25 — see Troubleshooting Log.
    params = {
        "query": address,
        "key": api_key,
        "dataset": "DPA",
        "maxresults": 1,
        "output_srs": "WGS84",
    }
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

    Query shape confirmed against https://www.planning.data.gov.uk/docs,
    2026-07-25 — see module docstring. Falls back to None (not a crash) if
    the lookup fails, per the roadmap's "resolver handles failure gracefully"
    success criterion.
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


async def resolve(address: str) -> ResolvedProperty:
    """
    Resolve a free-text UK property address to UPRN, coordinates, and local
    authority code. `polygon_wkt` on the result is always None — see module
    docstring VERIFICATION STATUS for why.

    Raises PropertyNotFoundError if the address cannot be matched.
    Raises ResolverServiceError on unexpected upstream failure.
    Never raises on missing local_authority_code — it degrades to None rather
    than failing the whole resolution, since downstream agents can still
    operate on UPRN + coordinates alone.
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
    match_score = dpa.get("MATCH")
    match_description = dpa.get("MATCH_DESCRIPTION")

    if uprn is None or lat is None or lon is None:
        raise ResolverServiceError(
            f"OS Places API returned an incomplete record for {address!r}: {dpa}"
        )

    local_authority_code = await _lookup_local_authority(lat, lon)

    return ResolvedProperty(
        uprn=str(uprn),
        address=matched_address,
        lat=float(lat),
        lon=float(lon),
        x_coordinate=float(x_coord) if x_coord is not None else None,
        y_coordinate=float(y_coord) if y_coord is not None else None,
        postcode=postcode,
        match_score=float(match_score) if match_score is not None else None,
        match_description=match_description,
        local_authority_code=local_authority_code,
        polygon_wkt=None,
    )
