"""
Tests for src/normalisation/normaliser.py.

DEF-02, FIXED 2026-08-06: conservation_area, tree_preservation_order,
listed_building and brownfield_land are now Optional[bool] on
PropertyRecord — None means the underlying query errored, distinct from a
clean False (confirmed absent from a working source). Several tests below
were rewritten, not just extended: the old
test_failed_dataset_surfaced_as_warning_not_silently_dropped asserted
`tree_preservation_order is False` for an errored dataset — that was DEF-02's
exact failure mode, demonstrated directly in a test that treated it as
correct behaviour. It now asserts None.
"""
from datetime import datetime, timezone

from src.adapters.hmlr_llc1 import LLC1Charge, LLC1Result
from src.adapters.historic_england import HistoricEnglandResult
from src.agents.planning_agent import DatasetResult, PlanningDataResult
from src.normalisation.normaliser import normalise

_NOW = datetime(2026, 8, 6, 12, 0, 0, tzinfo=timezone.utc)


def _empty_planning_result(**overrides: DatasetResult) -> PlanningDataResult:
    """Build a PlanningDataResult with every dataset defaulting to a clean,
    no-error, no-match result (status "negative"), overridden selectively
    per test."""
    datasets = [
        "planning-application", "conservation-area", "article-4-direction",
        "tree-preservation-order", "listed-building", "enforcement-notice",
        "brownfield-land",
    ]
    results = {
        d: DatasetResult(dataset=d, retrieved_at=_NOW, entities=[])
        for d in datasets
    }
    results.update(overrides)
    return PlanningDataResult(lat=51.0, lon=-2.0, results=results)


def _blocked_llc1(borough: str = "bristol") -> LLC1Result:
    return LLC1Result(
        borough=borough, uprn="67678", coverage_flag="manual",
        retrieved_at=_NOW,
        charges=[], blocked_reason="HMLR Business Gateway blocked",
    )


def _no_listed_building() -> HistoricEnglandResult:
    return HistoricEnglandResult(listed_building=False, retrieved_at=_NOW)


def _listed_building_query_error() -> HistoricEnglandResult:
    return HistoricEnglandResult(
        listed_building=None, retrieved_at=_NOW, error="NHLE query failed: timeout",
    )


def test_normalise_happy_path_all_sources_present():
    planning = _empty_planning_result(
        **{
            "planning-application": DatasetResult(
                "planning-application", _NOW,
                [{"reference": "2024/0123/FUL", "name": "Extension"}],
            ),
            "conservation-area": DatasetResult(
                "conservation-area", _NOW, [{"name": "Clifton Conservation Area"}]
            ),
            "article-4-direction": DatasetResult(
                "article-4-direction", _NOW, [{"name": "A4 Direction"}]
            ),
            "tree-preservation-order": DatasetResult(
                "tree-preservation-order", _NOW, [{"name": "TPO 12"}]
            ),
            "listed-building": DatasetResult(
                "listed-building", _NOW, [{"reference": "1234567"}]
            ),
        }
    )
    he = HistoricEnglandResult(
        listed_building=True, retrieved_at=_NOW, grade="Grade II", list_entry="1234567",
    )
    llc1 = LLC1Result(
        borough="bristol", uprn="67678", coverage_flag="manual", retrieved_at=_NOW,
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
    PropertyRecord.article_4_direction's docstring. Deliberately different
    from tree_preservation_order below even on a clean, error-free result:
    Article 4 is never treated as authoritative here at all, so even a
    clean negative isn't meaningful.
    """
    planning = _empty_planning_result()
    record = normalise("bristol", _blocked_llc1(), _no_listed_building(), planning)

    assert record.article_4_direction is None
    assert record.article_4_direction is not False


def test_tree_preservation_order_not_found_is_false_not_none_when_the_query_was_clean():
    """
    Contrast with Article 4 above: TPO's source IS treated as authoritative,
    so a clean, error-free query returning nothing is a genuine negative
    answer, not an unconfirmed one.
    """
    planning = _empty_planning_result()
    record = normalise("bristol", _blocked_llc1(), _no_listed_building(), planning)

    assert record.tree_preservation_order is False


def test_tree_preservation_order_is_none_not_false_when_the_query_errored():
    """
    DEF-02, the fix made concrete: an errored TPO query must not read as a
    confirmed "no TPO" on a CON29 field. This replaces what
    test_failed_dataset_surfaced_as_warning_not_silently_dropped used to
    assert (tree_preservation_order is False for this exact scenario) —
    that was the bug, demonstrated directly in a test.
    """
    planning = _empty_planning_result(
        **{"tree-preservation-order": DatasetResult(
            "tree-preservation-order", _NOW, [], error="HTTP 500"
        )}
    )
    record = normalise("bristol", _blocked_llc1(), _no_listed_building(), planning)

    assert record.tree_preservation_order is None
    assert record.tree_preservation_order is not False


def test_brownfield_land_is_none_not_false_when_the_query_errored():
    """Same fix as tree_preservation_order, same reasoning."""
    planning = _empty_planning_result(
        **{"brownfield-land": DatasetResult(
            "brownfield-land", _NOW, [], error="HTTP 503"
        )}
    )
    record = normalise("bristol", _blocked_llc1(), _no_listed_building(), planning)

    assert record.brownfield_land is None
    assert record.brownfield_land is not False


def test_conservation_area_is_none_not_false_when_the_query_errored():
    """
    conservation_area used len(entities_for(...)) > 0 rather than has_any()
    literally, but carried the identical DEF-02 bug under a different
    spelling — an errored query has empty entities, same as a clean
    negative, so it also collapsed to False before this fix.
    """
    planning = _empty_planning_result(
        **{"conservation-area": DatasetResult(
            "conservation-area", _NOW, [], error="HTTP 500"
        )}
    )
    record = normalise("bristol", _blocked_llc1(), _no_listed_building(), planning)

    assert record.conservation_area is None
    assert record.conservation_area_name is None


def test_listed_building_conflict_detected_when_sources_disagree():
    planning = _empty_planning_result(
        **{"listed-building": DatasetResult("listed-building", _NOW, [])}
    )
    he = HistoricEnglandResult(listed_building=True, retrieved_at=_NOW, grade="II", list_entry="999")

    record = normalise("bristol", _blocked_llc1(), he, planning)

    assert record.listed_building is True  # HE's positive wins
    assert record.listed_building_source_conflict is True
    assert any("conflict" in w.lower() for w in record.warnings)


def test_listed_building_agreement_no_conflict():
    planning = _empty_planning_result(
        **{"listed-building": DatasetResult("listed-building", _NOW, [{"reference": "999"}])}
    )
    he = HistoricEnglandResult(listed_building=True, retrieved_at=_NOW, grade="II", list_entry="999")

    record = normalise("bristol", _blocked_llc1(), he, planning)

    assert record.listed_building is True
    assert record.listed_building_source_conflict is False


def test_listed_building_both_sources_erroring_is_none_not_false():
    planning = _empty_planning_result(
        **{"listed-building": DatasetResult("listed-building", _NOW, [], error="HTTP 500")}
    )
    record = normalise("bristol", _blocked_llc1(), _listed_building_query_error(), planning)

    assert record.listed_building is None
    # Neither source resolved cleanly, so this is missing data, not a
    # cross-source disagreement — no conflict should be raised.
    assert record.listed_building_source_conflict is False


def test_listed_building_one_source_positive_other_errored_is_true_not_held_back():
    """
    Documented, deliberate behaviour (see PropertyRecord.listed_building's
    docstring): a genuine positive from a working source is not suppressed
    just because the other source failed. No conflict is raised either —
    conflict detection requires both sources to have resolved cleanly.
    """
    planning = _empty_planning_result(
        **{"listed-building": DatasetResult("listed-building", _NOW, [], error="HTTP 500")}
    )
    he = HistoricEnglandResult(listed_building=True, retrieved_at=_NOW, grade="II", list_entry="999")

    record = normalise("bristol", _blocked_llc1(), he, planning)

    assert record.listed_building is True
    assert record.listed_building_source_conflict is False


def test_llc1_passthrough_preserves_charges_and_blocked_reason():
    llc1 = LLC1Result(
        borough="hackney", uprn="10008231087", coverage_flag="manual", retrieved_at=_NOW,
        charges=[LLC1Charge(charge_type="Light obstruction notice", description="test")],
        blocked_reason="Hackney not migrated to LLC1",
    )
    planning = _empty_planning_result()

    record = normalise("hackney", llc1, _no_listed_building(), planning)

    assert record.llc1_coverage_flag == "manual"
    assert len(record.llc1_charges) == 1
    assert record.llc1_charges[0].charge_type == "Light obstruction notice"
    assert record.llc1_blocked_reason == "Hackney not migrated to LLC1"


def test_failed_dataset_surfaced_as_warning_and_degrades_to_none_not_a_false_positive():
    """
    REWRITTEN 2026-08-06 (DEF-02): previously asserted
    `tree_preservation_order is False` for this exact scenario — an errored
    dataset reading as a confirmed negative was the bug this test used to
    document as correct behaviour. It now asserts the fix: the warning is
    still surfaced (that part was always right), but the field degrades to
    None, not a false negative.
    """
    planning = _empty_planning_result(
        **{"tree-preservation-order": DatasetResult(
            "tree-preservation-order", _NOW, [], error="HTTP 500"
        )}
    )
    record = normalise("bristol", _blocked_llc1(), _no_listed_building(), planning)

    assert any("tree-preservation-order" in w and "HTTP 500" in w for w in record.warnings)
    assert record.tree_preservation_order is None


def test_historic_england_error_is_surfaced_as_a_warning():
    planning = _empty_planning_result()
    record = normalise("bristol", _blocked_llc1(), _listed_building_query_error(), planning)

    assert any("Historic England" in w and "timeout" in w for w in record.warnings)


def test_normalise_never_raises_on_fully_empty_inputs():
    """The normaliser is the layer everything funnels through — it must
    handle the most degraded case (nothing found anywhere, HMLR blocked)
    without raising, same as every adapter it sits downstream of. All
    inputs here are clean (no errors), so False/None below reflect the
    Article-4-vs-everything-else distinction, not error handling — see the
    dedicated error-path tests above for that."""
    planning = _empty_planning_result()
    record = normalise("hackney", _blocked_llc1("hackney"), _no_listed_building(), planning)

    assert record.listed_building is False
    assert record.article_4_direction is None
    assert record.tree_preservation_order is False
    assert record.llc1_coverage_flag == "manual"


def test_normalise_never_raises_when_every_dataset_and_historic_england_error():
    """
    The genuinely degraded case, not the clean-empty one above: every
    planning.data.gov.uk dataset errors AND Historic England errors. This is
    the actual graceful-degradation claim Sprint 1's design rests on — not
    raising under total, simultaneous failure, not just under a clean "found
    nothing" result.
    """
    datasets = [
        "planning-application", "conservation-area", "article-4-direction",
        "tree-preservation-order", "listed-building", "enforcement-notice",
        "brownfield-land",
    ]
    planning = PlanningDataResult(
        lat=51.0, lon=-2.0,
        results={
            d: DatasetResult(dataset=d, retrieved_at=_NOW, entities=[], error="HTTP 500")
            for d in datasets
        },
    )

    record = normalise(
        "hackney", _blocked_llc1("hackney"), _listed_building_query_error(), planning
    )

    assert record.conservation_area is None
    assert record.article_4_direction is None
    assert record.tree_preservation_order is None
    assert record.listed_building is None
    assert record.brownfield_land is None
    assert record.listed_building_source_conflict is False
    assert record.llc1_coverage_flag == "manual"
    assert len(record.warnings) == len(datasets) + 1  # every dataset + Historic England
