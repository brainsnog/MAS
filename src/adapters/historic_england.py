"""
Historic England adapter — listed buildings (National Heritage List for
England, NHLE).

Covers CON29 question 3.5 — see src/con29_registry.py.

STATUS: no API key expected to be required. Confirmed via search 2026-07-22
(see CON29_ROADMAP_v2.md Architecture Decisions): NHLE listed-buildings data
is published as open data under the Open Government Licence via a public
ArcGIS FeatureServer:

    https://services-eu1.arcgis.com/ZOdPfBS3aqqDYPUQ/arcgis/rest/services/
    National_Heritage_List_for_England_NHLE_v02_VIEW/FeatureServer

LAYER DISCOVERY — CONFIRMED against a real call 2026-07-25 (Griff ran
`?f=json` directly): this service has 11 layers; two of them match "listed
building" — id 0 "Listed Building points" and id 3 "Listed Building
polygons". `_discover_listed_building_layer_id` explicitly prefers the
points layer (Historic England's own field descriptions say the polygon
layer only covers buildings listed/amended since 4 April 2011, so it is NOT
the comprehensive one) rather than relying on which happens to come first in
the array. Layer names use plain spaces, not underscores, so that specific
earlier worry didn't materialise. This part of the original verification gap
is now resolved.

REMAINING, LOWER-RISK GAP: the exact attribute-key casing returned by a real
`/0/query` call (e.g. whether the grade field comes back as "Grade",
"GRADE", "grade", or something else) is still unconfirmed — the `?f=json`
call above lists layers, not their fields. `_find_attr` already matches
case-insensitively by substring specifically to absorb this uncertainty, so
this is a lower-risk item than the layer discovery was; worth confirming on
Sprint 1's first real end-to-end run rather than requiring another separate
verification step right now.

DEF-09, RESOLVED 2026-08-06 — never-raise contract: this adapter used to
raise HistoricEnglandServiceError on discovery/query failure, the only one
of the four adapters/agents that did (planning_agent, gis_agent, hmlr_llc1
already returned an `error`-carrying result; property_resolver is the one
adapter allowed to raise, since it's a precondition, not a data source).
Fixed to match: every failure path now returns a HistoricEnglandResult with
`error` set and `listed_building=None` (not False — DEF-02's discipline
applies here too: an error must never look like a confirmed "not listed").
`HistoricEnglandServiceError` is deleted; nothing raises it any more.

The `_listed_building_layer_id` module-level cache was examined before this
change, not assumed safe: a network/parse failure during discovery leaves
the cache at `None` (the exception fires before either cache-write line), so
it already self-heals on the next call. A "discovery succeeded, no layer
matched" result sets the cache to `-1` permanently — sticky, but harmless
under both the old and new contract, since every subsequent call already
produces the identical outcome either way (previously the same raised
exception; now the same `error`-carrying result). This change does not
touch that caching behaviour. Worth acknowledging rather than treating as
fully closed, though: the sticky case means a transient upstream change (a
layer rename, a partial response caught mid-deploy) stays cached for the
life of the process either way. That was equally true under the old
contract for a short-lived CLI invocation, where it barely mattered — but
Sprint 6 runs a long-lived Gradio process, where "until restart" becomes a
real duration, not a per-invocation non-issue.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from src.redaction import redact_url

FEATURE_SERVER_URL = (
    "https://services-eu1.arcgis.com/ZOdPfBS3aqqDYPUQ/arcgis/rest/services/"
    "National_Heritage_List_for_England_NHLE_v02_VIEW/FeatureServer"
)

# CON29 questions this adapter is the primary_source for, per con29_registry.py.
COVERS_QUESTIONS: tuple[str, ...] = ("3.5",)

DEFAULT_RADIUS_M = 50

# Populated lazily by _discover_listed_building_layer_id, cached for the life
# of the process. None means "not yet looked up"; -1 means "looked up, not
# found" (so we don't retry a failed discovery on every call). See module
# docstring DEF-09 note for why this caching is unchanged by the never-raise
# fix, and its acknowledged limitation for a long-lived Sprint 6 process.
_listed_building_layer_id: Optional[int] = None


@dataclass(frozen=True)
class HistoricEnglandResult:
    # None means "not determined due to an error" — distinct from a
    # confirmed False, same discipline as DEF-02 elsewhere in this project.
    listed_building: Optional[bool]
    # Required, not Optional: every call attempts at least the discovery
    # request, so there is always a real retrieval moment to timestamp.
    # Always construct with datetime.now(timezone.utc) — a dataclass field
    # cannot enforce timezone-awareness the way CON29Field's AwareDatetime
    # does, so a naive datetime would pass here silently.
    retrieved_at: datetime
    grade: Optional[str] = None
    list_entry: Optional[str] = None
    name: Optional[str] = None
    match_count: int = 0
    source_name: str = "Historic England — National Heritage List for England (NHLE)"
    # The actual resolved request URL for whichever call was last attempted
    # (discovery or query), redacted per DEF-04. NHLE is keyless today, so
    # redaction is a no-op in practice — applied anyway for consistency and
    # in case that ever changes.
    source_url: Optional[str] = None
    error: Optional[str] = None
    covers_questions: tuple[str, ...] = COVERS_QUESTIONS


async def _discover_listed_building_layer_id(client: httpx.AsyncClient) -> Optional[int]:
    global _listed_building_layer_id
    if _listed_building_layer_id is not None:
        return _listed_building_layer_id if _listed_building_layer_id != -1 else None

    resp = await client.get(FEATURE_SERVER_URL, params={"f": "json"})
    resp.raise_for_status()
    payload = resp.json()

    candidates = [
        layer for layer in payload.get("layers", [])
        if "listed building" in (layer.get("name") or "").lower()
    ]
    if not candidates:
        _listed_building_layer_id = -1
        return None

    # Confirmed via a real call to FeatureServer?f=json (2026-07-25): this
    # service has BOTH "Listed Building points" (id 0) and "Listed Building
    # polygons" (id 3). The points layer must be chosen explicitly, not
    # picked up by accident because it happens to come first in the array
    # (which is what the previous version of this function effectively
    # relied on) — Historic England's own published field descriptions say
    # the polygon layer only covers buildings listed or substantively
    # amended since 4 April 2011, so it is NOT the comprehensive layer.
    points_layer = next((l for l in candidates if "point" in l["name"].lower()), None)
    chosen = points_layer or candidates[0]
    _listed_building_layer_id = chosen["id"]
    return _listed_building_layer_id


def _find_attr(attributes: dict, *substrings: str) -> Optional[str]:
    """Case-insensitive substring match over attribute keys — see module
    docstring for why exact key casing isn't assumed."""
    for key, value in attributes.items():
        key_lower = key.lower()
        if any(s in key_lower for s in substrings) and value not in (None, ""):
            return str(value)
    return None


def _discovery_source_url() -> str:
    return redact_url(str(httpx.URL(FEATURE_SERVER_URL, params={"f": "json"})))


async def get_listed_building_status(
    lat: float, lon: float, radius_m: float = DEFAULT_RADIUS_M
) -> HistoricEnglandResult:
    """
    Check whether a point is within `radius_m` metres of a listed building.

    Never raises — see module docstring DEF-09. "not found" and "confirmed
    not listed" (listed_building=False) are valid, expected outcomes; a
    genuine upstream problem (service down, bad response shape) returns
    listed_building=None with `error` set, never False.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            layer_id = await _discover_listed_building_layer_id(client)
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
            return HistoricEnglandResult(
                listed_building=None,
                retrieved_at=datetime.now(timezone.utc),
                source_url=_discovery_source_url(),
                error=f"Could not discover the Listed Buildings layer: {exc}",
            )

        if layer_id is None:
            return HistoricEnglandResult(
                listed_building=None,
                retrieved_at=datetime.now(timezone.utc),
                source_url=_discovery_source_url(),
                error=(
                    "No layer matching 'listed building' found on the NHLE "
                    "FeatureServer — the service's layer names may have "
                    "changed. See module docstring VERIFICATION GAP."
                ),
            )

        params = {
            "f": "json",
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "distance": radius_m,
            "units": "esriSRUnit_Meter",
            "outFields": "*",
            "returnGeometry": "false",
        }
        query_url = f"{FEATURE_SERVER_URL}/{layer_id}/query"
        source_url = redact_url(str(httpx.URL(query_url, params=params)))
        try:
            resp = await client.get(query_url, params=params)
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
            return HistoricEnglandResult(
                listed_building=None,
                retrieved_at=datetime.now(timezone.utc),
                source_url=source_url,
                error=f"NHLE query failed: {exc}",
            )

    features = payload.get("features", [])
    retrieved_at = datetime.now(timezone.utc)
    if not features:
        return HistoricEnglandResult(
            listed_building=False,
            retrieved_at=retrieved_at,
            match_count=0,
            source_url=source_url,
        )

    attrs = features[0].get("attributes", {})
    grade = _find_attr(attrs, "grade")
    list_entry = _find_attr(attrs, "listentry", "list_entry", "list entry")
    name = _find_attr(attrs, "name") or _find_attr(attrs, "feature_name")

    return HistoricEnglandResult(
        listed_building=True,
        retrieved_at=retrieved_at,
        grade=grade,
        list_entry=list_entry,
        name=name,
        match_count=len(features),
        source_url=source_url,
    )
