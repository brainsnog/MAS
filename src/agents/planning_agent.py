"""
Planning Data Agent — queries planning.data.gov.uk BY POINT across every
dataset relevant to Sprint 1's Bucket-1 CON29 coverage.

Covers CON29 questions per CON29_ROADMAP_v2.md Sprint 1 §C (corrected
2026-07-25): 1.1a-g, 1.2, 1.1h, 3.7, 3.5 (cross-check with Historic England),
3.13 (partial), 3.11.

ARCHITECTURE NOTE (2026-07-25): queries by POINT (latitude/longitude), not
polygon — see Architecture Decisions & Changes: there is no boundary/polygon
dataset on planning.data.gov.uk and no free source of a property's own
parcel polygon. This reuses the exact query shape already confirmed correct
in property_resolver.py's _lookup_local_authority
(dataset=X&longitude=..&latitude=..).

ON THE 1.1h/ARTICLE-4 OVERLAP WITH BUCKET 2 (not a bug, a deliberate note):
CON29_ROADMAP_v2.md's own field classification table lists Article 4
directions (1.1h-i) under Bucket 2 (agent_navigated / council website), yet
this Sprint 1 agent also queries planning.data.gov.uk's
"article-4-direction" dataset for the same question. This is consistent
with the system's own source-reliability hierarchy (try the highest-tier
source first, fall back to lower tiers): if the national dataset happens to
have this council's Article 4 data, that's a genuine Bucket-1-quality hit;
if it comes back empty, that does NOT mean no Article 4 direction exists —
it means fall through to the council-website / Bucket 2 path, which isn't
built by this agent. Downstream (normalisation / mapper) needs to treat an
empty result here as "not found in this source", not "confirmed absent".

VERIFICATION GAP: entities are passed through largely as-is (whatever keys
planning.data.gov.uk returns per entity — reference, name, entry-date, etc.)
rather than parsed field-by-field, since the exact extra fields available
per dataset (e.g. a planning application's decision outcome) were not
confirmed against live docs. That interpretation is Sprint 1 §D
(normalisation layer) or Sprint 3 (mapper)'s job, not this agent's.

Minor note, not a bug: the roadmap's own Sprint 1 §C table lists 1.1g under
BOTH "planning-application" and "enforcement-notice" datasets. Kept faithful
to that as written; the normalisation layer may see the same question
answered from two datasets and should treat that as corroborating evidence,
not a conflict to flag.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional

import httpx

PLANNING_DATA_BASE_URL = "https://www.planning.data.gov.uk/entity.json"

# dataset -> CON29 question IDs it primarily (or opportunistically, for
# 1.1h — see module docstring) answers, per CON29_ROADMAP_v2.md Sprint 1 §C.
DATASET_TO_QUESTIONS: dict[str, tuple[str, ...]] = {
    "planning-application": ("1.1a", "1.1b", "1.1c", "1.1d", "1.1e", "1.1f", "1.1g"),
    "conservation-area": ("1.2", "3.11"),
    "article-4-direction": ("1.1h",),
    "tree-preservation-order": ("3.7",),
    "listed-building": ("3.5",),
    "enforcement-notice": ("1.1g",),
    "brownfield-land": ("3.13",),
}


@dataclass
class DatasetResult:
    dataset: str
    entities: list[dict] = field(default_factory=list)
    # Populated instead of raising — see get_planning_data(). A failure on
    # one dataset must not take down the others.
    error: Optional[str] = None


@dataclass
class PlanningDataResult:
    lat: float
    lon: float
    results: dict[str, "DatasetResult"] = field(default_factory=dict)

    def entities_for(self, dataset: str) -> list[dict]:
        r = self.results.get(dataset)
        return r.entities if r else []

    def has_any(self, dataset: str) -> bool:
        return len(self.entities_for(dataset)) > 0

    def failed_datasets(self) -> list[str]:
        return [d for d, r in self.results.items() if r.error is not None]


async def _query_dataset(
    client: httpx.AsyncClient, dataset: str, lat: float, lon: float
) -> DatasetResult:
    params = {"dataset": dataset, "latitude": lat, "longitude": lon}
    try:
        resp = await client.get(PLANNING_DATA_BASE_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()
        entities = payload.get("entities") or payload.get("results") or []
        return DatasetResult(dataset=dataset, entities=entities)
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
        # Same graceful-degradation principle as property_resolver.py's
        # _lookup_local_authority: one dataset failing shouldn't abort the
        # others. Recorded on the result so the caller can see exactly
        # which dataset(s) failed without losing the ones that succeeded.
        return DatasetResult(dataset=dataset, entities=[], error=str(exc))


async def get_planning_data(lat: float, lon: float) -> PlanningDataResult:
    """
    Query every dataset in DATASET_TO_QUESTIONS by point (lat/lon), in
    parallel. Never raises — see DatasetResult.error / failed_datasets().
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        dataset_results = await asyncio.gather(
            *[_query_dataset(client, dataset, lat, lon) for dataset in DATASET_TO_QUESTIONS]
        )

    return PlanningDataResult(
        lat=lat,
        lon=lon,
        results={r.dataset: r for r in dataset_results},
    )
