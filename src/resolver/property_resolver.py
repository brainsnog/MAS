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

DEF-03, FIXED 2026-08-06: `ResolvedProperty` was missing `borough`,
`search_id`, and the OS Places address components (`BUILDING_NUMBER`,
`SUB_BUILDING_NAME`, `BUILDING_NAME`, `THOROUGHFARE_NAME`, `POST_TOWN`),
which are present in the DPA response and were thrown away in favour of the
concatenated `ADDRESS` string. There was also no mapping from
`local_authority_code` to a `Borough` literal, and no rejection path for
out-of-scope addresses.

`local_authority_code` now holds planning.data.gov.uk's `organisation-entity`
value (an int identifying the owning council — 66 for Bristol City Council,
163 for London Borough of Hackney, both confirmed live in Handoff Section
3.5), NOT the `reference`/`name` string fields the previous version read.
Decision, not a technical necessity: the previous local-authority-district
test double fabricated `"reference": "bristol"` — an invented value, never
confirmed against a real response — whereas organisation-entity 66/163 are
values this project has actually seen returned by planning.data.gov.uk (on
the brownfield-land dataset; not yet confirmed specifically on
local-authority-district's own response shape, which is why
`_lookup_local_authority` degrades to None rather than raising if the field
is absent, same graceful-degradation treatment as every other failure mode
here).

`resolve()` raises `PropertyOutOfScopeError` when the local authority lookup
succeeds AND resolves to an organisation-entity that is confirmed to be
neither Bristol nor Hackney — a positive, confident signal the property is
somewhere this system doesn't support. It does NOT raise when the lookup
merely fails or returns nothing (network error, dataset miss, or the field
being absent from the response) — that already degrades to
`local_authority_code=None`/`borough=None`, same as before this fix,
preserving `resolve()`'s existing "never raises on missing
local_authority_code" behaviour for the genuinely-unknown case. Only a
confirmed wrong answer raises; an absent one doesn't.

DEF-04, FIXED 2026-08-06: the OS Places request URL carries the API key as a
query parameter (`key=...`). `source_url` captures the actual resolved
request URL, redacted via `src.redaction.redact_url` before it ever reaches
`ResolvedProperty` — never store the raw one. `retrieved_at` is a required,
aware `datetime` (`datetime.now(timezone.utc)`), matching the contract now
shared by all four adapters/agents.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import httpx

from src.models import Borough
from src.redaction import redact_url

OS_PLACES_BASE_URL = "https://api.os.uk/search/places/v1/find"
PLANNING_DATA_BASE_URL = "https://www.planning.data.gov.uk/entity.json"

# Confirmed live, Handoff Section 3.5 (2026-08-05 discovery session).
_BOROUGH_BY_ORGANISATION_ENTITY: dict[int, Borough] = {
    66: "bristol",
    163: "hackney",
}


class PropertyNotFoundError(Exception):
    """Raised when the address cannot be resolved to a UPRN."""


class ResolverServiceError(Exception):
    """Raised on an unexpected upstream error (non-2xx, timeout, bad payload)."""


class PropertyOutOfScopeError(Exception):
    """
    Raised when the resolved local authority is confirmed to be neither
    Bristol nor Hackney — the two boroughs this system supports. NOT raised
    when the local authority simply couldn't be determined (see module
    docstring DEF-03) — only a confident wrong answer raises.
    """


@dataclass
class ResolvedProperty:
    uprn: str
    address: str
    lat: float
    lon: float
    x_coordinate: Optional[float]
    y_coordinate: Optional[float]
    postcode: Optional[str]
    # DEF-03: per-search identifier. Generated with uuid4() if the caller
    # doesn't supply one — see resolve()'s own docstring. No orchestrator
    # exists yet to own a canonical per-search id, so the resolver
    # generates a sensible default rather than requiring one that has
    # nowhere else to come from yet.
    search_id: str
    # DEF-04: required, aware datetime — never a string. Always construct
    # with datetime.now(timezone.utc); a dataclass field cannot enforce
    # timezone-awareness the way CON29Field's AwareDatetime does.
    retrieved_at: datetime
    match_score: Optional[float] = None
    match_description: Optional[str] = None
    # DEF-03: organisation-entity value, not the previous version's
    # fabricated "reference" string — see module docstring.
    local_authority_code: Optional[int] = None
    borough: Optional[Borough] = None
    # DEF-03: OS Places DPA address components, previously discarded in
    # favour of only the concatenated ADDRESS string.
    building_number: Optional[str] = None
    sub_building_name: Optional[str] = None
    building_name: Optional[str] = None
    thoroughfare_name: Optional[str] = None
    post_town: Optional[str] = None
    # DEF-04: the actual resolved OS Places request URL, redacted.
    source_url: Optional[str] = None
    # Not sourced by this resolver — see Architecture Decisions & Changes,
    # 2026-07-25, in CON29_ROADMAP_v2.md. No free/open source of a property's
    # own parcel polygon exists (that's HMLR's licensed INSPIRE Index Polygons).
    # Downstream agents query planning.data.gov.uk by point (lat/lon) instead.
    # Kept as a field in case a licensed polygon source is added later.
    polygon_wkt: Optional[str] = None


async def _call_os_places_find(address: str, api_key: str) -> tuple[dict, str]:
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
    source_url = redact_url(str(httpx.URL(OS_PLACES_BASE_URL, params=params)))
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

    return results[0]["DPA"], source_url


async def _lookup_local_authority(lat: float, lon: float) -> Optional[int]:
    """
    Look up the local-authority-district entity containing this point and
    return its organisation-entity value — see module docstring DEF-03 for
    why this reads organisation-entity, not reference/name.

    Query shape confirmed against https://www.planning.data.gov.uk/docs,
    2026-07-25 — see module docstring. Falls back to None (not a crash) if
    the lookup fails OR if the entity is present but has no
    organisation-entity field, per the roadmap's "resolver handles failure
    gracefully" success criterion.
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
                value = entities[0].get("organisation-entity")
                return int(value) if value is not None else None
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError, KeyError):
            return None
    return None


async def resolve(address: str, search_id: Optional[str] = None) -> ResolvedProperty:
    """
    Resolve a free-text UK property address to UPRN, coordinates, address
    components, and borough. `polygon_wkt` on the result is always None —
    see module docstring VERIFICATION STATUS for why.

    `search_id` is generated with uuid4() if not supplied — see
    ResolvedProperty.search_id's own docstring.

    Raises PropertyNotFoundError if the address cannot be matched.
    Raises ResolverServiceError on unexpected upstream failure.
    Raises PropertyOutOfScopeError if the address resolves to a confirmed
    local authority outside Bristol/Hackney — see module docstring DEF-03.
    Never raises on a merely UNDETERMINED local_authority_code/borough — it
    degrades to None rather than failing the whole resolution, since
    downstream agents can still operate on UPRN + coordinates alone.
    """
    api_key = os.environ.get("OS_PLACES_API_KEY")
    if not api_key:
        raise ResolverServiceError(
            "OS_PLACES_API_KEY not set. Add the OS Places API product to your "
            "OS Data Hub account and store the key as a Codespace secret."
        )

    dpa, source_url = await _call_os_places_find(address, api_key)

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
    borough = (
        _BOROUGH_BY_ORGANISATION_ENTITY.get(local_authority_code)
        if local_authority_code is not None
        else None
    )
    if local_authority_code is not None and borough is None:
        raise PropertyOutOfScopeError(
            f"Resolved local authority organisation-entity "
            f"{local_authority_code} is neither Bristol (66) nor Hackney "
            f"(163) — {address!r} is outside this system's supported scope."
        )

    return ResolvedProperty(
        uprn=str(uprn),
        address=matched_address,
        lat=float(lat),
        lon=float(lon),
        x_coordinate=float(x_coord) if x_coord is not None else None,
        y_coordinate=float(y_coord) if y_coord is not None else None,
        postcode=postcode,
        search_id=search_id or str(uuid4()),
        retrieved_at=datetime.now(timezone.utc),
        match_score=float(match_score) if match_score is not None else None,
        match_description=match_description,
        local_authority_code=local_authority_code,
        borough=borough,
        building_number=dpa.get("BUILDING_NUMBER"),
        sub_building_name=dpa.get("SUB_BUILDING_NAME"),
        building_name=dpa.get("BUILDING_NAME"),
        thoroughfare_name=dpa.get("THOROUGHFARE_NAME"),
        post_town=dpa.get("POST_TOWN"),
        source_url=source_url,
        polygon_wkt=None,
    )
