"""
Normalisation Layer — maps HMLR, Historic England, and Planning Data Agent
outputs into a canonical PropertyRecord. Pure rules, no LLM, no network
calls, per CON29_ROADMAP_v2.md Sprint 1 §D.

PropertyRecord is a deliberately intermediate model, not the final
CON29Field / PropertySearchResult schema (that's Sprint 3's job, in a
src/models.py that doesn't exist yet). It exists so Sprint 1's three
adapters/agents have one common, canonical shape to land in before the
Sprint 3 mapper turns it into actual CON29 question answers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from src.adapters.hmlr_llc1 import LLC1Charge, LLC1Result
from src.adapters.historic_england import HistoricEnglandResult
from src.agents.planning_agent import PlanningDataResult
from src.normalisation.terminology_map import normalise_grade

Borough = Literal["bristol", "hackney"]


@dataclass
class PropertyRecord:
    borough: Borough

    # --- Planning applications & enforcement (1.1a-f; enforcement notices
    # are real-form 3.9(a) — see planning_agent.py RESOLVED 2026-08-03) ---
    planning_applications: list[dict] = field(default_factory=list)
    planning_enforcement_notices: list[dict] = field(default_factory=list)

    # --- Conservation area (1.2, 3.11) ---
    conservation_area: bool = False
    conservation_area_name: Optional[str] = None

    # --- Article 4 direction ---
    # RESOLVED 2026-08-03: Article 4 directions have no standalone CON29
    # Part 1 question number in the real form (con29_registry.py, rebuilt
    # 2026-08-02 against a real exemplar) — plausibly an LLC1 Part 1 charge
    # instead. See planning_agent.py's / gis_agent.py's NON_CON29_DATASETS.
    # None (NOT False) still means "not found in this source" — not
    # "confirmed absent". Sprint 3's mapper must not map this field onto any
    # CON29Field until the LLC1-vs-CON29 question is resolved.
    article_4_direction: Optional[bool] = None

    # --- Tree preservation order (3.9m) ---
    # RESOLVED 2026-08-03: real-form 3.9(m), a sub-item of "Notices, orders,
    # directions and proceedings under Planning Acts" — not a standalone
    # "3.7" as originally assumed (real 3.7 is "Outstanding Notices",
    # unrelated). Bucket 1 (auto) unchanged — no equivalent ambiguity to
    # Article 4's above. True/False here is treated as a real (if
    # imperfect) answer, not "unconfirmed either way".
    tree_preservation_order: bool = False

    # --- Listed building (3.5) — cross-checked between two sources, per
    # Sprint 1 §C's own instruction ("dataset=listed-building -> CON29 3.5
    # (cross-check with HE)") ---
    listed_building: bool = False
    listed_building_grade: Optional[str] = None
    listed_building_list_entry: Optional[str] = None
    listed_building_source_conflict: bool = False

    # --- Brownfield land (3.13, partial coverage per roadmap) ---
    brownfield_land: bool = False

    # --- LLC1 (3.1, 3.12) — passthrough from the HMLR adapter ---
    llc1_coverage_flag: Literal["manual", "auto"] = "manual"
    llc1_charges: list[LLC1Charge] = field(default_factory=list)
    llc1_blocked_reason: Optional[str] = None

    # --- Traceability: anything worth a human/the Sprint 3 mapper seeing
    # that doesn't fit a specific field above (dataset failures, conflicts
    # between sources). Deliberately free-text and additive, never used to
    # suppress or override the structured fields above it. ---
    warnings: list[str] = field(default_factory=list)


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
    ca_entities = planning.entities_for("conservation-area")
    record.conservation_area = len(ca_entities) > 0
    record.conservation_area_name = ca_entities[0].get("name") if ca_entities else None

    # --- Article 4 direction — None, not False, when not found (see field docstring) ---
    record.article_4_direction = True if planning.has_any("article-4-direction") else None

    # --- Tree preservation order — plain True/False, no "unconfirmed" state ---
    record.tree_preservation_order = planning.has_any("tree-preservation-order")

    # --- Listed building — cross-check Historic England against
    # planning.data.gov.uk's own listed-building dataset ---
    he_says_listed = historic_england.listed_building
    planning_says_listed = planning.has_any("listed-building")

    record.listed_building = he_says_listed or planning_says_listed
    if he_says_listed:
        record.listed_building_grade = normalise_grade(historic_england.grade)
        record.listed_building_list_entry = historic_england.list_entry

    if he_says_listed != planning_says_listed:
        record.listed_building_source_conflict = True
        record.warnings.append(
            "Listed building status conflict: Historic England says "
            f"{he_says_listed}, planning.data.gov.uk's listed-building "
            f"dataset says {planning_says_listed}"
        )

    # --- Brownfield land (partial coverage, per roadmap) ---
    record.brownfield_land = planning.has_any("brownfield-land")

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

    return record
