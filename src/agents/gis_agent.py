"""
GIS Agent — borough-specific spatial layers, dispatched by borough.

Covers CON29 questions 3.9(m) (tree preservation orders — see RESOLVED
2026-08-03 below), 1.2/3.11 (conservation area — Hackney only here, since
Bristol's is already opportunistically covered by planning_agent.py's
national planning.data.gov.uk query), and 3.13 (contaminated land — Hackney
only, partial). Article 4 directions are also queried (both boroughs) but do
NOT map to a CON29 question — see NON_CON29_DATASETS below.

ARCHITECTURE NOTE (2026-08-02): Bristol and Hackney do NOT share a GIS
backend — see CON29_ROADMAP_v2.md Architecture Decisions. Bristol runs a
legacy ArcGIS Server (MapServer, REST). Hackney runs GeoServer (WFS 2.0),
not ArcGIS at all — discovered by inspecting the config the Hackney public
tree map itself loads client-side, not assumed by analogy with Bristol. This
module therefore has two backend query functions (_query_arcgis, _query_wfs)
behind one per-borough dispatcher, the same shape as hmlr_llc1.py's
per-borough branching.

Real endpoints and layer names below were confirmed 2026-08-02 via real
discovery calls (Griff ran them, same discipline as historic_england.py's
`?f=json` layer discovery):
  Bristol:  https://maps2.bristol.gov.uk/server2/rest/services/ext/INSPIRE/MapServer
            (?f=json — full 19-layer list; see BRISTOL_LAYER_IDS)
  Hackney:  https://map2.hackney.gov.uk/geoserver/ows
            (WFS 2.0 GetCapabilities — ~700 layers; see HACKNEY_LAYERS)

A near-miss worth recording: a generic web search for Bristol's "INSPIRE
MapServer" surfaces an identically-named service run by a different council
(City of London) on the same vendor template, with completely different
layer IDs. The layer IDs below come only from Bristol's own confirmed
`?f=json` response — never assume a same-named service elsewhere shares
numbering.

TPO QUERY DESIGN (confirmed with Griff 2026-08-02): buffer approach, 15m
radius (TPO_BUFFER_M below) — same shape as historic_england.py's
radius/distance pattern, not "does the point fall exactly under this
canopy/trunk feature". A tight point-in-feature test is less forgiving of
the property resolver's own address-matching imprecision (see
ResolvedProperty.match_score in property_resolver.py) than CON29 3.9(m) —
"is this property affected by a tree preservation order" — actually requires.

RESOLVED 2026-08-03 — TPO/ARTICLE-4 NUMBERING (previously flagged in
CON29_ROADMAP_v2.md's Current State, held pending confirmation):
  - Tree preservation orders are real-form question 3.9(m), confirmed
    against the real St Albans exemplar and con29_registry.py's rebuild
    (2026-08-02) — NOT a standalone "3.7" as this module originally assumed.
    DATASET_TO_QUESTIONS now reads "3.9m".
  - Article 4 directions have no standalone CON29 Part 1 question number in
    the real form. Rather than leave the previous (confirmed wrong) "1.1h"
    mapping in place, or silently drop Article 4 querying altogether,
    "article_4_direction" has moved to NON_CON29_DATASETS below: still
    queried (real, useful evidence-manifest content — a council's Article 4
    layer is genuine data worth surfacing even without a CON29 question
    number), but explicitly NOT claimed to answer any CON29Field. Sprint 3's
    CON29 Mapper must not map this dataset onto a CON29 question until this
    is confirmed one way or the other (most likely: Article 4 directions
    register as an LLC1 Part 1 charge rather than a CON29 enquiry at all,
    which would mean hmlr_llc1.py's eventual LLC1 parsing is the right home
    for this data, not the CON29 Mapper).

KNOWN GAPS, not build failures — recorded as DatasetResult.unavailable_reason
(no network call attempted), same transparency principle as hmlr_llc1.py's
blocked_reason stubs:
  - Bristol has no confirmed source here for Rights of Way (2.2-2.5) or
    Contaminated Land (3.13). Both plausibly exist on Bristol's MODERN
    ArcGIS Hub (open-data-bristol-bcc.hub.arcgis.com — confirmed to have a
    "Public Rights of Way" dataset), not this legacy INSPIRE MapServer, but
    the real FeatureServer URL for that Hub item is not yet confirmed.
  - Hackney has no confirmed Rights of Way source anywhere — the full
    ~700-layer WFS GetCapabilities response was searched for anything
    resembling a definitive map / footpath / bridleway layer and none was
    found. Treated as a genuine digital-maturity finding worth keeping in
    the dissertation, not a bug to keep chasing.

REMAINING, LOWER-RISK GAP (same category as historic_england.py's
attribute-casing note): the exact geometry column name on Hackney's WFS
layers has not been confirmed via a real DescribeFeatureType call.
HACKNEY_GEOM_FIELD below defaults to "geom" — the column name seen in the
greenspaces:single_tree_area_3857 CSV export from the same GeoServer
instance, so it's evidence-backed, but not yet confirmed for the specific
planning:/pollution: layers this module queries. A DescribeFeatureType call
attempted 2026-08-02 returned only an unfollowed wrapper document — two
ready-made follow-up URLs are with Griff. Confirm on Sprint 2's first real
end-to-end Hackney run.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Literal, Optional

import httpx

Borough = Literal["bristol", "hackney"]

# Confirmed with Griff 2026-08-02 — see module docstring TPO QUERY DESIGN.
TPO_BUFFER_M = 15

# --- Bristol (legacy ArcGIS Server, MapServer) --------------------------

BRISTOL_MAPSERVER_URL = (
    "https://maps2.bristol.gov.uk/server2/rest/services/ext/INSPIRE/MapServer"
)

# Real layer IDs, captured 2026-08-02 via a real ?f=json call against
# BRISTOL_MAPSERVER_URL (19 layers total). See module docstring near-miss
# note before ever reusing IDs from a similarly-named service elsewhere.
BRISTOL_LAYER_IDS: dict[str, int] = {
    "article_4_direction": 1,
    # "Tree preservation order - trunk" (point layer) — deliberately NOT the
    # "canopy" polygon layer (id 17), per the buffer-based TPO design above.
    "tree_preservation_order": 18,
}

# --- Hackney (GeoServer, WFS 2.0) ---------------------------------------

HACKNEY_WFS_URL = "https://map2.hackney.gov.uk/geoserver/ows"

# Real typeNames, confirmed 2026-08-02 via a real WFS GetCapabilities call.
# All native EPSG:27700 — the "_3857" variants that also exist on this
# server are cartographic-only, built for the public vector-tile map; do
# not query those here.
HACKNEY_LAYERS: dict[str, str] = {
    "tree_preservation_order": "planning:tpo_point_as_area",
    "article_4_direction": "planning:article_4_direction",
    "conservation_area": "planning:conservation_area",
    "brownfield_register": "planning:brownfield_register",
    "contaminated_land_part2a_investigated": "pollution:part2a_site_investigated",
    "contaminated_land_part2a_concern": "pollution:part2a_site_potential_concern",
}

# See module docstring REMAINING, LOWER-RISK GAP.
HACKNEY_GEOM_FIELD = "geom"

# dataset key -> CON29 question IDs it answers, per con29_registry.py.
# article_4_direction is deliberately NOT here — see NON_CON29_DATASETS.
DATASET_TO_QUESTIONS: dict[str, tuple[str, ...]] = {
    "tree_preservation_order": ("3.9m",),
    "conservation_area": ("1.2", "3.11"),  # Hackney only, see _get_hackney_gis_data
    "brownfield_register": ("3.13",),  # Hackney only
    "contaminated_land_part2a_investigated": ("3.13",),  # Hackney only
    "contaminated_land_part2a_concern": ("3.13",),  # Hackney only
    "rights_of_way": ("2.2", "2.3", "2.4", "2.5"),  # both boroughs, both unavailable
}

# Datasets this agent queries that do NOT answer a numbered CON29 Part 1
# question — kept separate from DATASET_TO_QUESTIONS rather than mapped to
# a guessed ID, same "flag, don't invent" discipline as con29_registry.py's
# UNCONFIRMED_NUMBERING list. See module docstring RESOLVED 2026-08-03.
NON_CON29_DATASETS: dict[str, str] = {
    "article_4_direction": (
        "No standalone CON29 Part 1 question for Article 4 directions was "
        "found in the real St Albans exemplar (2026-08-02) — plausibly an "
        "LLC1 Part 1 charge (Local Land Charges Rules 1977) rather than a "
        "CON29 enquiry. Still queried for evidence-manifest purposes; "
        "Sprint 3's CON29 Mapper must not map it onto any CON29Field until "
        "this is confirmed one way or the other."
    ),
}

# See module docstring KNOWN GAPS.
_BRISTOL_UNAVAILABLE: dict[str, str] = {
    "rights_of_way": (
        "No confirmed source in this MapServer (ext/INSPIRE, 19 layers, "
        "captured 2026-08-02). Bristol's modern ArcGIS Hub "
        "(open-data-bristol-bcc.hub.arcgis.com) has a 'Public Rights of "
        "Way' dataset but its real FeatureServer URL is not yet confirmed."
    ),
    "contaminated_land": (
        "No confirmed source in this MapServer or the modern ArcGIS Hub as "
        "of 2026-08-02. Falls to coverage_flag unavailable pending a "
        "confirmed source."
    ),
}
_HACKNEY_UNAVAILABLE: dict[str, str] = {
    "rights_of_way": (
        "No layer resembling a definitive map / footpath / bridleway found "
        "across Hackney's full WFS GetCapabilities response (~700 layers, "
        "captured 2026-08-02). Treated as a genuine digital-maturity "
        "finding, not a build gap — see CON29_ROADMAP_v2.md Architecture "
        "Decisions."
    ),
}


@dataclass
class DatasetResult:
    dataset: str
    features: list[dict] = field(default_factory=list)
    # Populated instead of raising on a genuine fetch failure — see the
    # query functions below. A failure on one dataset must not take down
    # the others, same principle as planning_agent.py's DatasetResult.
    error: Optional[str] = None
    # Populated instead of attempting a call at all, for a KNOWN GAP (see
    # module docstring) — distinct from `error`, which means "we tried and
    # it failed". Mirrors hmlr_llc1.py's blocked_reason.
    unavailable_reason: Optional[str] = None


@dataclass
class GisDataResult:
    borough: Borough
    lat: float
    lon: float
    results: dict[str, DatasetResult] = field(default_factory=dict)

    def features_for(self, dataset: str) -> list[dict]:
        r = self.results.get(dataset)
        return r.features if r else []

    def has_any(self, dataset: str) -> bool:
        return len(self.features_for(dataset)) > 0

    def failed_datasets(self) -> list[str]:
        return [d for d, r in self.results.items() if r.error is not None]

    def unavailable_datasets(self) -> list[str]:
        return [d for d, r in self.results.items() if r.unavailable_reason is not None]


async def _query_arcgis(
    client: httpx.AsyncClient,
    dataset: str,
    layer_id: int,
    lat: float,
    lon: float,
    distance_m: float = 0,
) -> DatasetResult:
    """
    Query a Bristol MapServer layer by point, exactly the same query shape
    as historic_england.py's get_listed_building_status — inSR 4326 passed
    directly regardless of the service's own native spatial reference
    (27700 here), letting ArcGIS reproject server-side.

    distance_m=0 means an exact intersects test (used for polygon
    designation layers like Article 4, where the property point must fall
    inside the designated area, not just near it). A nonzero distance_m
    buffers the test (used for the TPO trunk point layer — see module
    docstring TPO QUERY DESIGN).
    """
    params = {
        "f": "json",
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "false",
    }
    if distance_m:
        params["distance"] = distance_m
        params["units"] = "esriSRUnit_Meter"
    try:
        resp = await client.get(f"{BRISTOL_MAPSERVER_URL}/{layer_id}/query", params=params)
        resp.raise_for_status()
        payload = resp.json()
        features = [f.get("attributes", {}) for f in payload.get("features", [])]
        return DatasetResult(dataset=dataset, features=features)
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
        return DatasetResult(dataset=dataset, features=[], error=str(exc))


async def _query_wfs(
    client: httpx.AsyncClient,
    dataset: str,
    type_name: str,
    lat: float,
    lon: float,
    buffer_m: float = 0,
) -> DatasetResult:
    """
    Query a Hackney GeoServer WFS 2.0 layer by point, using an
    SRID-qualified CQL geometry so the point (WGS84) can be filtered
    against a layer stored natively in EPSG:27700 without a client-side
    reprojection step — GeoServer handles the transform. Confirmed as a
    documented GeoServer CQL capability; not yet exercised against a real
    response (see module docstring REMAINING, LOWER-RISK GAP alongside the
    geometry-field-name one).

    buffer_m=0 uses INTERSECTS (used for polygon designation layers).
    A nonzero buffer_m uses DWITHIN (used for TPO — see module docstring).
    """
    point = f"SRID=4326;POINT({lon} {lat})"
    if buffer_m:
        cql_filter = f"DWITHIN({HACKNEY_GEOM_FIELD},{point},{buffer_m},meters)"
    else:
        cql_filter = f"INTERSECTS({HACKNEY_GEOM_FIELD},{point})"
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": type_name,
        "outputFormat": "application/json",
        "CQL_FILTER": cql_filter,
    }
    try:
        resp = await client.get(HACKNEY_WFS_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()
        features = [f.get("properties", {}) for f in payload.get("features", [])]
        return DatasetResult(dataset=dataset, features=features)
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
        return DatasetResult(dataset=dataset, features=[], error=str(exc))


async def get_gis_data(borough: Borough, lat: float, lon: float) -> GisDataResult:
    """
    Dispatch to the correct borough backend. Never raises — every dataset
    result is either a successful (possibly empty) match, a fetch error, or
    a known-unavailable stub; see DatasetResult.
    """
    if borough == "bristol":
        return await _get_bristol_gis_data(lat, lon)
    return await _get_hackney_gis_data(lat, lon)


async def _get_bristol_gis_data(lat: float, lon: float) -> GisDataResult:
    async with httpx.AsyncClient(timeout=10.0) as client:
        tpo_result, article4_result = await asyncio.gather(
            _query_arcgis(
                client, "tree_preservation_order",
                BRISTOL_LAYER_IDS["tree_preservation_order"],
                lat, lon, distance_m=TPO_BUFFER_M,
            ),
            _query_arcgis(
                client, "article_4_direction",
                BRISTOL_LAYER_IDS["article_4_direction"],
                lat, lon,
            ),
        )

    results = {
        "tree_preservation_order": tpo_result,
        "article_4_direction": article4_result,
        "rights_of_way": DatasetResult(
            dataset="rights_of_way",
            unavailable_reason=_BRISTOL_UNAVAILABLE["rights_of_way"],
        ),
        "contaminated_land": DatasetResult(
            dataset="contaminated_land",
            unavailable_reason=_BRISTOL_UNAVAILABLE["contaminated_land"],
        ),
    }
    return GisDataResult(borough="bristol", lat=lat, lon=lon, results=results)


async def _get_hackney_gis_data(lat: float, lon: float) -> GisDataResult:
    async with httpx.AsyncClient(timeout=10.0) as client:
        (
            tpo_result,
            article4_result,
            conservation_result,
            brownfield_result,
            part2a_investigated_result,
            part2a_concern_result,
        ) = await asyncio.gather(
            _query_wfs(
                client, "tree_preservation_order",
                HACKNEY_LAYERS["tree_preservation_order"],
                lat, lon, buffer_m=TPO_BUFFER_M,
            ),
            _query_wfs(
                client, "article_4_direction",
                HACKNEY_LAYERS["article_4_direction"], lat, lon,
            ),
            _query_wfs(
                client, "conservation_area",
                HACKNEY_LAYERS["conservation_area"], lat, lon,
            ),
            _query_wfs(
                client, "brownfield_register",
                HACKNEY_LAYERS["brownfield_register"], lat, lon,
            ),
            _query_wfs(
                client, "contaminated_land_part2a_investigated",
                HACKNEY_LAYERS["contaminated_land_part2a_investigated"], lat, lon,
            ),
            _query_wfs(
                client, "contaminated_land_part2a_concern",
                HACKNEY_LAYERS["contaminated_land_part2a_concern"], lat, lon,
            ),
        )

    results = {
        "tree_preservation_order": tpo_result,
        "article_4_direction": article4_result,
        "conservation_area": conservation_result,
        "brownfield_register": brownfield_result,
        "contaminated_land_part2a_investigated": part2a_investigated_result,
        "contaminated_land_part2a_concern": part2a_concern_result,
        "rights_of_way": DatasetResult(
            dataset="rights_of_way",
            unavailable_reason=_HACKNEY_UNAVAILABLE["rights_of_way"],
        ),
    }
    return GisDataResult(borough="hackney", lat=lat, lon=lon, results=results)
