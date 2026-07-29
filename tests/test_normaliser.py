from src.adapters.hmlr_llc1 import LLC1Charge, LLC1Result
from src.adapters.historic_england import HistoricEnglandResult
from src.agents.planning_agent import DatasetResult, PlanningDataResult
from src.normalisation.normaliser import normalise


def _empty_planning_result(**overrides: DatasetResult) -> PlanningDataResult:
    """Build a PlanningDataResult with every dataset defaulting to empty/no
    error, overridden selectively per test."""
    datasets = [
        "planning-application", "conservation-area", "article-4-direction",
        "tree-preservation-order", "listed-building", "enforcement-notice",
        "brownfield-land",
    ]
    results = {d: DatasetResult(dataset=d, entities=[]) for d in datasets}
    results.update(overrides)
    return PlanningDataResult(lat=51.0, lon=-2.0, results=results)


def _blocked_llc1(borough: str = "bristol") -> LLC1Result:
    return LLC1Result(
        borough=borough, uprn="67678", coverage_flag="manual",
        charges=[], blocked_reason="HMLR Business Gateway blocked",
    )


def _no_listed_building() -> HistoricEnglandResult:
    return HistoricEnglandResult(listed_building=False)


def test_normalise_happy_path_all_sources_present():
    planning = _empty_planning_result(
        **{
            "planning-application": DatasetResult(
                "planning-application",
                [{"reference": "2024/0123/FUL", "name": "Extension"}],
            ),
            "conservation-area": DatasetResult(
                "conservation-area", [{"name": "Clifton Conservation Area"}]
            ),
            "article-4-direction": DatasetResult(
                "article-4-direction", [{"name": "A4 Direction"}]
            ),
            "tree-preservation-order": DatasetResult(
                "tree-preservation-order", [{"name": "TPO 12"}]
            ),
            "listed-building": DatasetResult(
                "listed-building", [{"reference": "1234567"}]
            ),
        }
    )
    he = HistoricEnglandResult(listed_building=True, grade="Grade II", list_entry="1234567")
    llc1 = LLC1Result(
        borough="bristol", uprn="67678", coverage_flag="manual",
        blocked_reason="HMLR Business Gateway blocked",
    )

    record = normalise("bristol", llc1, he, planning)

    assert record.borough == "bristol"
    assert len(record.planning_applications) == 1
    assert record.conservation_area is True
    assert record.conservation_area_name == "Clifton Conservation Area"
    assert record.article_4_direction is True
    assert record.tree_preservation_order is True
    assert record.listed_building is True
    assert record.listed_building_grade == "II"  # normalised from "Grade II"
    assert record.listed_building_list_entry == "1234567"
    assert record.listed_building_source_conflict is False
    assert record.llc1_coverage_flag == "manual"
    assert record.llc1_blocked_reason == "HMLR Business Gateway blocked"
    assert record.warnings == []


def test_article_4_not_found_is_none_not_false():
    """
    Critical semantic: an empty article-4-direction dataset result must
    become None (unconfirmed), not False (confirmed absent) — see
    PropertyRecord.article_4_direction's docstring. This must never regress
    to False, since a caller treating None as False would be asserting
    something the system doesn't actually know.
    """
    planning = _empty_planning_result()
    record = normalise("bristol", _blocked_llc1(), _no_listed_building(), planning)

    assert record.article_4_direction is None
    assert record.article_4_direction is not False


def test_tree_preservation_order_not_found_is_false_not_none():
    """
    Contrast with Article 4 above: TPO is Bucket 1 (auto) with no Bucket-2
    fallback ambiguity in the roadmap's own classification, so an empty
    result here is treated as a real False, not an unconfirmed None.
    """
    planning = _empty_planning_result()
    record = normalise("bristol", _blocked_llc1(), _no_listed_building(), planning)

    assert record.tree_preservation_order is False


def test_listed_building_conflict_detected_when_sources_disagree():
    planning = _empty_planning_result(
        **{"listed-building": DatasetResult("listed-building", [])}
    )
    he = HistoricEnglandResult(listed_building=True, grade="II", list_entry="999")

    record = normalise("bristol", _blocked_llc1(), he, planning)

    assert record.listed_building is True  # HE's positive wins
    assert record.listed_building_source_conflict is True
    assert any("conflict" in w.lower() for w in record.warnings)


def test_listed_building_agreement_no_conflict():
    planning = _empty_planning_result(
        **{"listed-building": DatasetResult("listed-building", [{"reference": "999"}])}
    )
    he = HistoricEnglandResult(listed_building=True, grade="II", list_entry="999")

    record = normalise("bristol", _blocked_llc1(), he, planning)

    assert record.listed_building is True
    assert record.listed_building_source_conflict is False


def test_llc1_passthrough_preserves_charges_and_blocked_reason():
    llc1 = LLC1Result(
        borough="hackney", uprn="10008231087", coverage_flag="manual",
        charges=[LLC1Charge(charge_type="Light obstruction notice", description="test")],
        blocked_reason="Hackney not migrated to LLC1",
    )
    planning = _empty_planning_result()

    record = normalise("hackney", llc1, _no_listed_building(), planning)

    assert record.llc1_coverage_flag == "manual"
    assert len(record.llc1_charges) == 1
    assert record.llc1_charges[0].charge_type == "Light obstruction notice"
    assert record.llc1_blocked_reason == "Hackney not migrated to LLC1"


def test_failed_dataset_surfaced_as_warning_not_silently_dropped():
    planning = _empty_planning_result(
        **{"tree-preservation-order": DatasetResult(
            "tree-preservation-order", [], error="HTTP 500"
        )}
    )
    record = normalise("bristol", _blocked_llc1(), _no_listed_building(), planning)

    assert any("tree-preservation-order" in w and "HTTP 500" in w for w in record.warnings)
    # A failed dataset still degrades to a safe default rather than crashing
    # or (worse) claiming a false positive:
    assert record.tree_preservation_order is False


def test_normalise_never_raises_on_fully_empty_inputs():
    """The normaliser is the layer everything funnels through — it must
    handle the most degraded case (nothing found anywhere, HMLR blocked)
    without raising, same as every adapter it sits downstream of."""
    planning = _empty_planning_result()
    record = normalise("hackney", _blocked_llc1("hackney"), _no_listed_building(), planning)

    assert record.listed_building is False
    assert record.article_4_direction is None
    assert record.tree_preservation_order is False
    assert record.llc1_coverage_flag == "manual"
