"""
Normalisation Layer — maps HMLR, Historic England, and Planning Data Agent
outputs into a canonical PropertyRecord. Pure rules, no LLM, no network
calls, per CON29_ROADMAP_v2.md Sprint 1 §D.

PropertyRecord is a deliberately intermediate model, not the final
CON29Field / PropertySearchResult schema (Sprint 3's job, src/models.py,
built WP-01 2026-08-06). It exists so Sprint 1's three adapters/agents have
one common, canonical shape to land in before the Sprint 3 mapper turns it
into actual CON29 question answers.

DEF-02, FIXED 2026-08-06: this file used to call planning.has_any(dataset)
(and, for conservation_area, len(entities_for(dataset)) > 0 — the same bug
under a different name) to populate tree_preservation_order,
listed_building, brownfield_land and conservation_area as plain `bool`
fields. Both collapse "queried successfully, no record" and "the query
failed" to the same False — an errored TPO/brownfield/conservation-area
query would read as a confirmed negative on a CON29 field. Article 4 was
already correct (True or None, never False), because it was deliberately
built that way for a different reason: planning.data.gov.uk was never
treated as authoritative for Article 4 at all, so even a clean negative
wasn't meaningful there. All four fields are now Optional[bool], routed
through PlanningDataResult.status_for()/GisDataResult.status_for() (the
DEF-02 tri-state) and src.disposition.disposition_for_dataset_status(),
rather than reimplementing an equivalent mapping locally. See
_bool_from_status below. Two different reasons can now produce the same
None on different fields — noted on each field, since PropertyRecord's
field types are read directly by WP-09's future mapper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from src.adapters.hmlr_llc1 import LLC1Charge, LLC1Result
from src.adapters.historic_england import HistoricEnglandResult
from src.agents.planning_agent import PlanningDataResult
from src.disposition import DatasetStatus, disposition_for_dataset_status
from src.normalisation.terminology_map import normalise_grade

Borough = Literal["bristol", "hackney"]

# disposition_for_dataset_status only ever returns three of the four
# Disposition values for a DatasetStatus input (never flagged_manual, which
# has no corresponding DatasetStatus) — this is total over that range.
_BOOL_BY_DISPOSITION: dict[str, Optional[bool]] = {
    "determinate_positive": True,
    "determinate_negative": False,
    "unavailable": None,
}


def _bool_from_status(status: DatasetStatus) -> Optional[bool]:
    """
    Maps a dataset's tri-state status onto Optional[bool] via
    src.disposition's canonical status->disposition mapping, rather than
    hand-rolling an equivalent if/elif per field. None means "not
    determined" — the caller is responsible for recording *why* (query
    error vs. source never authoritative) in the field's own docstring;
    this function only knows the status, not the reason.
    """
    return _BOOL_BY_DISPOSITION[disposition_for_dataset_status(status)]


@dataclass
class PropertyRecord:
    borough: Borough

    # --- Planning applications & enforcement (1.1a-f; enforcement notices
    # are real-form 3.9(a) — see planning_agent.py RESOLVED 2026-08-03) ---
    planning_applications: list[dict] = field(default_factory=list)
    planning_enforcement_notices: list[dict] = field(default_factory=list)

    # --- Conservation area (1.2, 3.11) ---
    # FIXED 2026-08-06 (DEF-02): was a plain bool (len(entities) > 0), the
    # same conflation as has_any() under a different name. None means the
    # conservation-area query itself errored — not determined, not a
    # confirmed absence.
    conservation_area: Optional[bool] = None
    conservation_area_name: Optional[str] = None

    # --- Article 4 direction ---
    # RESOLVED 2026-08-03: Article 4 directions have no standalone CON29
    # Part 1 question number in the real form (con29_registry.py, rebuilt
    # 2026-08-02 against a real exemplar) — plausibly an LLC1 Part 1 charge
    # instead. See planning_agent.py's / gis_agent.py's NON_CON29_DATASETS.
    # None here means "this source was never authoritative for Article 4 at
    # all" — a clean negative wouldn't be meaningful either, so True-or-None
    # is deliberate, not a query-failure artefact. Contrast with the other
    # Optional[bool] fields below, where None specifically means the query
    # errored. Sprint 3's mapper must not map this field onto any CON29Field
    # until the LLC1-vs-CON29 question is resolved.
    article_4_direction: Optional[bool] = None

    # --- Tree preservation order (3.9m) ---
    # FIXED 2026-08-06 (DEF-02): was a plain bool via has_any(), which
    # conflated "queried, no TPO found" with "the query failed". Unlike
    # Article 4, this source IS treated as authoritative for TPOs, so a
    # clean negative is a real answer (False) — None here means
    # specifically that the query errored, nothing else.
    tree_preservation_order: Optional[bool] = None

    # --- Listed building (3.5) — cross-checked between two sources, per
    # Sprint 1 §C's own instruction ("dataset=listed-building -> CON29 3.5
    # (cross-check with HE)") ---
    # FIXED 2026-08-06 (DEF-02): was a plain bool (he_says_listed or
    # planning_says_listed, both booleans from a has_any()/legacy-bool
    # source). None now means BOTH sources failed to resolve cleanly (no
    # positive from either, and at least one errored) — see normalise()'s
    # cross-check logic below for exactly when a conflict is flagged.
    # NOTE: True is returned whenever EITHER source is positive, even if the
    # other source errored — a positive result is never held back pending
    # confirmation from a source that isn't reachable. This means a
    # confident True can sit next to an evidence-manifest entry showing one
    # source unreachable, with no warning generated for that specific
    # combination (a warning IS generated for the source's own failure via
    # planning.failed_datasets()/historic_england.error below, just not one
    # calling out this particular True-despite-partial-evidence case).
    # Defensible — a genuine positive from a working source shouldn't be
    # suppressed because a second source happened to fail — but worth
    # stating explicitly rather than leaving implicit.
    listed_building: Optional[bool] = None
    listed_building_grade: Optional[str] = None
    listed_building_list_entry: Optional[str] = None
    listed_building_source_conflict: bool = False

    # --- Brownfield land (3.13, partial coverage per roadmap) ---
    # FIXED 2026-08-06 (DEF-02): same fix as tree_preservation_order above.
    brownfield_land: Optional[bool] = None

    # --- LLC1 (3.1, 3.12) — passthrough from the HMLR adapter ---
    llc1_coverage_flag: Literal["manual", "auto"] = "manual"
    llc1_charges: list[LLC1Charge] = field(default_factory=list)
    llc1_blocked_reason: Optional[str] = None

    # --- Traceability: anything worth a human/the Sprint 3 mapper seeing
    # that doesn't fit a specific field above (dataset failures, conflicts
    # between sources). Deliberately free-text and additive, never used to
    # suppress or override the structured fields above it. ---
    warnings: list[str] = field(default_factory=list)


def _historic_england_status(historic_england: HistoricEnglandResult) -> DatasetStatus:
    """
    HistoricEnglandResult.listed_building is already Optional[bool] under
    DEF-09's never-raise contract (None on error) — this just restates it
    as a DatasetStatus so it can go through the same _bool_from_status path
    as everything else, rather than being handled by a separate convention.
    """
    if historic_england.listed_building is None:
        return "error"
    return "positive" if historic_england.listed_building else "negative"


def normalise(
    borough: Borough,
    llc1: LLC1Result,
    historic_england: HistoricEnglandResult,
    planning: PlanningDataResult,
) -> PropertyRecord:
    """
    Combine the three Sprint 1 adapter/agent outputs into one canonical
    PropertyRecord. Pure rules — no LLM, no network calls. Must not raise on
    any combination of valid adapter outputs, including ones representing
    partial/blocked/empty data: that graceful-degradation principle is the
    whole point of Sprint 1's design, and the normaliser is the layer
    everything funnels through, so it can't be where it breaks down.
    """
    record = PropertyRecord(borough=borough)

    # --- Planning applications & enforcement ---
    record.planning_applications = planning.entities_for("planning-application")
    record.planning_enforcement_notices = planning.entities_for("enforcement-notice")

    # --- Conservation area ---
    ca_status = planning.status_for("conservation-area")
    record.conservation_area = _bool_from_status(ca_status)
    if ca_status == "positive":
        ca_entities = planning.entities_for("conservation-area")
        record.conservation_area_name = ca_entities[0].get("name") if ca_entities else None

    # --- Article 4 direction — None, not False, when not found (see field docstring) ---
    record.article_4_direction = True if planning.status_for("article-4-direction") == "positive" else None

    # --- Tree preservation order — see field docstring for the None cases ---
    record.tree_preservation_order = _bool_from_status(planning.status_for("tree-preservation-order"))

    # --- Listed building — cross-check Historic England against
    # planning.data.gov.uk's own listed-building dataset. A conflict is only
    # flagged when BOTH sources resolved cleanly and disagree — an error on
    # either side is missing data, not a conflict. ---
    he_status = _historic_england_status(historic_england)
    planning_status = planning.status_for("listed-building")

    if he_status == "positive" or planning_status == "positive":
        record.listed_building = True
    elif he_status == "error" or planning_status == "error":
        record.listed_building = None
    else:
        record.listed_building = False

    if he_status == "positive":
        record.listed_building_grade = normalise_grade(historic_england.grade)
        record.listed_building_list_entry = historic_england.list_entry

    if he_status != "error" and planning_status != "error" and he_status != planning_status:
        record.listed_building_source_conflict = True
        record.warnings.append(
            "Listed building status conflict: Historic England says "
            f"{he_status == 'positive'}, planning.data.gov.uk's "
            f"listed-building dataset says {planning_status == 'positive'}"
        )

    # --- Brownfield land (partial coverage, per roadmap) ---
    record.brownfield_land = _bool_from_status(planning.status_for("brownfield-land"))

    # --- LLC1 passthrough ---
    record.llc1_coverage_flag = llc1.coverage_flag
    record.llc1_charges = list(llc1.charges)
    record.llc1_blocked_reason = llc1.blocked_reason

    # --- Surface any dataset failures rather than silently dropping them ---
    for dataset in planning.failed_datasets():
        error = planning.results[dataset].error
        record.warnings.append(
            f"planning.data.gov.uk dataset '{dataset}' failed: {error}"
        )
    if historic_england.error is not None:
        record.warnings.append(
            f"Historic England query failed: {historic_england.error}"
        )

    return record
