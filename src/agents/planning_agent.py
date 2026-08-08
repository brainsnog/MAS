"""
Planning Data Agent — queries planning.data.gov.uk BY POINT across every
dataset relevant to Sprint 1's Bucket-1 CON29 coverage.

Covers CON29 questions 1.1a-f, 1.2, 3.9(m), 3.9(a), 3.5 (cross-check with
Historic England), 3.13 (partial), 3.11 — see RESOLVED 2026-08-03 below for
what changed from the original Sprint 1 assumptions. Also queries
article-4-direction, which does NOT map to a CON29 question — see
NON_CON29_DATASETS.

ARCHITECTURE NOTE (2026-07-25): queries by POINT (latitude/longitude), not
polygon — see Architecture Decisions & Changes: there is no boundary/polygon
dataset on planning.data.gov.uk and no free source of a property's own
parcel polygon. This reuses the exact query shape already confirmed correct
in property_resolver.py's _lookup_local_authority
(dataset=X&longitude=..&latitude=..).

RESOLVED 2026-08-03 — TPO/ARTICLE-4/ENFORCEMENT NUMBERING (previously
flagged in CON29_ROADMAP_v2.md's Current State, held pending confirmation,
after con29_registry.py was rebuilt 2026-08-02 against a real St Albans
CON29R/LLC1 exemplar):
  - Tree preservation orders are real-form 3.9(m), not a standalone "3.7".
  - Enforcement notices are real-form 3.9(a), not "1.1g" as previously
    assumed (real 1.1g is "a heritage partnership agreement" — a
    genuinely different, much rarer thing, for which this agent currently
    has no automated source; left uncovered rather than force-mapped).
  - "planning-application" now maps only to 1.1a-f (planning permission,
    listed building consent, conservation area consent, and the three
    certificate-of-lawfulness variants) — all things a general planning
    application record plausibly represents. 1.1g is deliberately absent
    from this tuple, not silently folded in.
  - Article 4 directions have no standalone CON29 Part 1 question number in
    the real form at all (plausibly an LLC1 Part 1 charge instead — see
    NON_CON29_DATASETS). The dataset is still queried (real, useful
    evidence-manifest content), just not claimed to answer a CON29Field.
  The previous "ON THE 1.1h/ARTICLE-4 OVERLAP" note below described a
  design that turned out to rest on a wrong premise (that 1.1h was Article
  4) — replaced by the note above rather than left in place with a caveat
  bolted on, since the entire premise, not just a detail, was wrong.

VERIFICATION GAP: entities are passed through largely as-is (whatever keys
planning.data.gov.uk returns per entity — reference, name, entry-date, etc.)
rather than parsed field-by-field, since the exact extra fields available
per dataset (e.g. a planning application's decision outcome) were not
confirmed against live docs. That interpretation is Sprint 1 §D
(normalisation layer) or Sprint 3 (mapper)'s job, not this agent's.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

from src.disposition import DatasetStatus
from src.redaction import redact_url

PLANNING_DATA_BASE_URL = "https://www.planning.data.gov.uk/entity.json"

# dataset -> CON29 question IDs it answers, per con29_registry.py (rebuilt
# 2026-08-02 against a real exemplar — see module docstring RESOLVED
# 2026-08-03). article-4-direction is deliberately NOT here — see
# NON_CON29_DATASETS. 1.1g (heritage partnership agreement) currently has
# no automated source at all and is not claimed by any dataset below.
DATASET_TO_QUESTIONS: dict[str, tuple[str, ...]] = {
    "planning-application": ("1.1a", "1.1b", "1.1c", "1.1d", "1.1e", "1.1f"),
    "conservation-area": ("1.2", "3.11"),
    "tree-preservation-order": ("3.9m",),
    "listed-building": ("3.5",),
    "enforcement-notice": ("3.9a",),
    "brownfield-land": ("3.13",),
}

# Datasets this agent queries that do NOT answer a numbered CON29 Part 1
# question — kept separate from DATASET_TO_QUESTIONS rather than mapped to
# a guessed ID, same "flag, don't invent" discipline as con29_registry.py's
# UNCONFIRMED_NUMBERING list and gis_agent.py's own NON_CON29_DATASETS.
NON_CON29_DATASETS: dict[str, str] = {
    "article-4-direction": (
        "No standalone CON29 Part 1 question for Article 4 directions was "
        "found in the real St Albans exemplar (2026-08-02) — plausibly an "
        "LLC1 Part 1 charge (Local Land Charges Rules 1977) rather than a "
        "CON29 enquiry. Still queried for evidence-manifest purposes; "
        "Sprint 3's CON29 Mapper must not map it onto any CON29Field until "
        "this is confirmed one way or the other."
    ),
}

# Every dataset this agent actually queries — the union of
# DATASET_TO_QUESTIONS (maps onto a confirmed CON29 question) and
# NON_CON29_DATASETS (queried anyway, for evidence-manifest completeness).
# get_planning_data() iterates this, NOT DATASET_TO_QUESTIONS directly, so
# moving article-4-direction out of the question-mapping dict doesn't stop
# it being fetched.
ALL_DATASETS: tuple[str, ...] = tuple(DATASET_TO_QUESTIONS) + tuple(NON_CON29_DATASETS)


@dataclass
class DatasetResult:
    dataset: str
    # DEF-04: required, not Optional — every dataset in ALL_DATASETS always
    # gets a real HTTP attempt (success or caught exception), so there is
    # always a real retrieval moment to timestamp. Always construct with
    # datetime.now(timezone.utc); a dataclass field cannot enforce
    # timezone-awareness the way CON29Field's AwareDatetime does, so a
    # naive datetime would pass here silently and only fail later, at
    # CON29Field construction (WP-09).
    retrieved_at: datetime
    entities: list[dict] = field(default_factory=list)
    # Populated instead of raising — see get_planning_data(). A failure on
    # one dataset must not take down the others.
    error: Optional[str] = None
    # The actual resolved request URL, redacted per DEF-04. This source has
    # no key/credential today (planning.data.gov.uk is keyless), so
    # redaction is a no-op in practice — applied anyway for consistency.
    source_url: Optional[str] = None


@dataclass
class PlanningDataResult:
    lat: float
    lon: float
    results: dict[str, "DatasetResult"] = field(default_factory=dict)

    def entities_for(self, dataset: str) -> list[dict]:
        r = self.results.get(dataset)
        return r.entities if r else []

    def status_for(self, dataset: str) -> DatasetStatus:
        """
        DEF-02: tri-state, replacing has_any(). "positive"/"negative" are
        both a successful query (a real record found, or confirmed none);
        "error" means the call failed and must never be read as a
        confirmed negative — see src/disposition.py, which maps this onto
        CON29Field's disposition.
        """
        r = self.results.get(dataset)
        if r is None or r.error is not None:
            return "error"
        return "positive" if r.entities else "negative"

    def failed_datasets(self) -> list[str]:
        return [d for d, r in self.results.items() if r.error is not None]


async def _query_dataset(
    client: httpx.AsyncClient, dataset: str, lat: float, lon: float
) -> DatasetResult:
    params = {"dataset": dataset, "latitude": lat, "longitude": lon}
    source_url = redact_url(str(httpx.URL(PLANNING_DATA_BASE_URL, params=params)))
    try:
        resp = await client.get(PLANNING_DATA_BASE_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()
        entities = payload.get("entities") or payload.get("results") or []
        return DatasetResult(
            dataset=dataset,
            retrieved_at=datetime.now(timezone.utc),
            entities=entities,
            source_url=source_url,
        )
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
        # Same graceful-degradation principle as property_resolver.py's
        # _lookup_local_authority: one dataset failing shouldn't abort the
        # others. Recorded on the result so the caller can see exactly
        # which dataset(s) failed without losing the ones that succeeded.
        return DatasetResult(
            dataset=dataset,
            retrieved_at=datetime.now(timezone.utc),
            entities=[],
            error=str(exc),
            source_url=source_url,
        )


async def get_planning_data(lat: float, lon: float) -> PlanningDataResult:
    """
    Query every dataset in ALL_DATASETS by point (lat/lon), in parallel —
    this includes both DATASET_TO_QUESTIONS (maps onto a CON29 question) and
    NON_CON29_DATASETS (queried anyway, doesn't map onto one — see module
    docstring). Never raises — see DatasetResult.error / failed_datasets().
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        dataset_results = await asyncio.gather(
            *[_query_dataset(client, dataset, lat, lon) for dataset in ALL_DATASETS]
        )

    return PlanningDataResult(
        lat=lat,
        lon=lon,
        results={r.dataset: r for r in dataset_results},
    )
