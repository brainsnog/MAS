"""
Lightweight regression test for scripts/tally_sprint1_coverage.py — locks in
the counts so a future change to COVERS_QUESTIONS / DATASET_TO_QUESTIONS
that accidentally drops coverage gets caught, rather than only being
noticed the next time someone runs the script by hand.

CORRECTED 2026-08-03: con29_registry.py was rebuilt 2026-08-02 against a
real CON29R exemplar, which showed several of Sprint 1's original group
IDs were wrong (see tally_sprint1_coverage.py's own module docstring).
Correcting them dropped the counts below (architectural 10 -> 8, functional
8 -> 6) — a real, honest consequence of fixing wrong IDs, not a
functionality loss: the same adapters make the same real API calls either
way. Sprint 1's own success criterion ("at least 10 CON29 question groups
for Bristol"), previously reported as met, is NO LONGER MET with the
corrected groups. Flagged here and in CON29_ROADMAP_v2.md rather than
silently adjusting the threshold to make this test pass quietly.
"""
from scripts.tally_sprint1_coverage import ALL_GROUPS, reachable_question_ids


def test_architectural_coverage_no_longer_meets_the_original_ten_group_claim():
    """
    Sprint 1 was closed on the strength of an architectural count of 10,
    which met the "at least 10" success criterion. Correcting the group IDs
    against the real CON29R form (2026-08-03) drops this to 8 — genuinely
    below the original criterion. This test locks in the corrected, honest
    number rather than re-asserting a claim that no longer holds; the
    Sprint 1 closure claim itself needs revisiting with Griff (see
    CON29_ROADMAP_v2.md Architecture Decisions), not silently patched over
    here.
    """
    reachable = reachable_question_ids()
    covered_groups = [label for label, ids in ALL_GROUPS.items() if ids & reachable]
    assert len(covered_groups) == 8


def test_functional_coverage_today_excludes_hmlr_blocked_groups():
    """
    HMLR-sourced groups (3.1, 3.12) are architecturally wired but must not
    be counted as functionally delivering real Bristol data while the
    Business Gateway blocker stands — this test exists so that fixing the
    HMLR blocker later is a deliberate, visible change to this count, not
    an accidental one.
    """
    from src.adapters import hmlr_llc1

    reachable = reachable_question_ids()
    hmlr_ids = set(hmlr_llc1.COVERS_QUESTIONS)
    covered_groups = [label for label, ids in ALL_GROUPS.items() if ids & reachable]
    hmlr_groups = [label for label, ids in ALL_GROUPS.items() if ids & hmlr_ids]
    functional = [g for g in covered_groups if g not in hmlr_groups]

    assert "3.1 (Land required for public purposes)" in hmlr_groups
    assert "3.12 (Compulsory purchase)" in hmlr_groups
    assert len(functional) == 6
