"""
Regression test for scripts/verify_section1.py's sub-question wiring figures,
which CON29_BUILD_HANDOFF.md Section 1 quotes directly. Locks in 18
architecturally-wired / 12 functional so a future change to COVERS_QUESTIONS
/ DATASET_TO_QUESTIONS that silently shifts these counts fails CI instead of
letting Section 1 drift from the code.

CORRECTED 2026-08-06: Section 1 originally read "14 of 63 architecturally
wired" — an arithmetic error where the functional adjustment (subtracting
the four rights-of-way stub IDs 2.2-2.5) had been applied to the
architectural count too. Rights of way IS architecturally wired; it just
never returns real data today. See the 2026-08-06 Deviation Log entry.
"""
from scripts.verify_section1 import architecturally_wired_ids, functional_ids


def test_architecturally_wired_is_eighteen_of_sixty_three():
    assert len(architecturally_wired_ids()) == 18


def test_functional_is_twelve_of_sixty_three():
    assert len(functional_ids()) == 12


def test_functional_is_a_subset_of_architecturally_wired():
    assert functional_ids() <= architecturally_wired_ids()


def test_rights_of_way_is_wired_but_not_functional():
    row_ids = {"2.2", "2.3", "2.4", "2.5"}
    wired = architecturally_wired_ids()
    functional = functional_ids()
    assert row_ids <= wired
    assert not (row_ids & functional)
