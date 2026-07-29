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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

FEATURE_SERVER_URL = (
    "https://services-eu1.arcgis.com/ZOdPfBS3aqqDYPUQ/arcgis/rest/services/"
    "National_Heritage_List_for_England_NHLE_v02_VIEW/FeatureServer"
)

# CON29 questions this adapter is the primary_source for, per con29_registry.py.
COVERS_QUESTIONS: tuple[str, ...] = ("3.5",)

DEFAULT_RADIUS_M = 50

# Populated lazily by _discover_listed_building_layer_id, cached for the life
# of the process. None means "not yet looked up"; -1 means "looked up, not
# found" (so we don't retry a failed discovery on every call).
_listed_building_layer_id: Optional[int] = None


class HistoricEnglandServiceError(Exception):
    """Raised on an unexpected upstream error (non-2xx, timeout, bad payload)."""


@dataclass(frozen=True)
class HistoricEnglandResult:
    listed_building: bool
    grade: Optional[str] = None
    list_entry: Optional[str] = None
    name: Optional[str] = None
    match_count: int = 0
    source_name: str = "Historic England — National Heritage List for England (NHLE)"
    source_url: str = FEATURE_SERVER_URL
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


async def get_listed_building_status(
    lat: float, lon: float, radius_m: float = DEFAULT_RADIUS_M
) -> HistoricEnglandResult:
    """
    Check whether a point is within `radius_m` metres of a listed building.

    Never raises on "not found" — returns listed_building=False, which is a
    valid, expected answer, not a failure. Raises HistoricEnglandServiceError
    only on a genuine upstream problem (service down, bad response shape),
    since that's different from "confirmed not listed".
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            layer_id = await _discover_listed_building_layer_id(client)
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
            raise HistoricEnglandServiceError(
                f"Could not discover the Listed Buildings layer: {exc}"
            ) from exc

        if layer_id is None:
            raise HistoricEnglandServiceError(
                "No layer matching 'listed building' found on the NHLE "
                "FeatureServer — the service's layer names may have changed. "
                "See module docstring VERIFICATION GAP."
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
        try:
            resp = await client.get(f"{FEATURE_SERVER_URL}/{layer_id}/query", params=params)
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
            raise HistoricEnglandServiceError(f"NHLE query failed: {exc}") from exc

    features = payload.get("features", [])
    if not features:
        return HistoricEnglandResult(listed_building=False, match_count=0)

    attrs = features[0].get("attributes", {})
    grade = _find_attr(attrs, "grade")
    list_entry = _find_attr(attrs, "listentry", "list_entry", "list entry")
    name = _find_attr(attrs, "name") or _find_attr(attrs, "feature_name")

    return HistoricEnglandResult(
        listed_building=True,
        grade=grade,
        list_entry=list_entry,
        name=name,
        match_count=len(features),
    )
