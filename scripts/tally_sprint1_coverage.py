"""
Sprint 1 coverage tally.

Cross-references what Sprint 1's built adapters/agents actually query for
against a table-row-level grouping (e.g. "1.1a-f" is one group, not six),
NOT against con29_registry.py's expanded sub-question IDs. Sprint 1's
success criterion ("covers at least 10 CON29 question groups for Bristol")
uses this table-row grouping, so that's what this counts against, for a
like-for-like comparison.

CORRECTED 2026-08-03 against con29_registry.py's 2026-08-02 rebuild (a real
St Albans CON29R/LLC1 exemplar): several groups below were previously wrong
and have been removed rather than left in place — "1.1g (Planning
enforcement)" (real 1.1g is a heritage partnership agreement, a different,
currently-uncovered question), the standalone "3.7 (Tree preservation
orders)" (TPO is real-form 3.9m, already inside the 3.9a-n group below,
not its own group), "1.1h-i (Article 4 directions)" (Article 4 has no
CON29 Part 1 question number at all in the real form — see
planning_agent.py's NON_CON29_DATASETS), "3.2 (Roadworks / traffic
schemes)" and the old "3.6 (Outstanding notices)" (both wrong IDs; the real
3.6 is Traffic Schemes and real 3.7 is Outstanding Notices, now correctly
split into "3.6a-l" and "3.7a-g" below).

This is a real, honest reduction in the group COUNT (24 -> 16), not a
reduction in what the system actually does — the same code makes the same
real API calls either way. What changed is which CON29 question IDs those
calls are honestly claimed to answer. Sprint 1's own "at least 10 groups"
success criterion, previously reported as met with a count of 10, is
RE-CHECKED below against the corrected groups — see main()'s output and
CON29_ROADMAP_v2.md's Architecture Decisions for whether it's still met.

Run: python3 -m scripts.tally_sprint1_coverage
"""

from src.adapters import historic_england, hmlr_llc1
from src.agents import planning_agent

# Table rows, as {group_label: {question_ids in this group}} — see module
# docstring CORRECTED 2026-08-03 for what changed and why.
BUCKET_1_GROUPS: dict[str, set[str]] = {
    "1.1a-f (Planning decisions and pending applications)": {"1.1a", "1.1b", "1.1c", "1.1d", "1.1e", "1.1f"},
    "1.2 (Planning designations)": {"1.2"},
    "2.2-2.5 (Public rights of way)": {"2.2", "2.3", "2.4", "2.5"},
    "3.1 (Land required for public purposes)": {"3.1"},
    "3.5 (Listed buildings)": {"3.5"},
    "3.9a-n (Notices, orders, directions and proceedings under Planning "
    "Acts -- includes tree preservation orders at 3.9m and enforcement "
    "notices at 3.9a)": {f"3.9{c}" for c in "abcdefghijklmn"},
    "3.10 (Community Infrastructure Levy)": {"3.10"},
    "3.11 (Conservation area designation)": {"3.11"},
    "3.12 (Compulsory purchase)": {"3.12"},
    "3.13 (Contaminated land)": {"3.13"},
    "3.14 (Radon)": {"3.14"},
    "3.15 (Assets of community value)": {"3.15"},
}

# Table rows for the agent-navigated bucket.
BUCKET_2_GROUPS: dict[str, set[str]] = {
    "1.1j-l (Building regulations, where published)": {"1.1j", "1.1k", "1.1l"},
    "2.1a (Highway adoption, where published)": {"2.1a"},
    "3.6a-l (Traffic Schemes)": {f"3.6{c}" for c in "abcdefghijkl"},
    "3.7a-g (Outstanding notices)": {f"3.7{c}" for c in "abcdefg"},
}

ALL_GROUPS: dict[str, set[str]] = {**BUCKET_1_GROUPS, **BUCKET_2_GROUPS}


def reachable_question_ids() -> set[str]:
    """
    Union of every CON29 question ID Sprint 1's built code queries for,
    regardless of whether it's currently blocked (HMLR). Article 4 is
    deliberately excluded here — see planning_agent.py's NON_CON29_DATASETS
    and module docstring RESOLVED 2026-08-03; it's still queried by the real
    code, just no longer claimed to answer a CON29 question.
    """
    ids: set[str] = set()
    ids.update(hmlr_llc1.COVERS_QUESTIONS)
    ids.update(historic_england.COVERS_QUESTIONS)
    for questions in planning_agent.DATASET_TO_QUESTIONS.values():
        ids.update(questions)
    return ids


def main() -> None:
    reachable = reachable_question_ids()
    hmlr_ids = set(hmlr_llc1.COVERS_QUESTIONS)

    architecturally_covered = sorted(
        label for label, ids in ALL_GROUPS.items() if ids & reachable
    )
    hmlr_groups = sorted(
        label for label, ids in ALL_GROUPS.items() if ids & hmlr_ids
    )
    functionally_covered_today = sorted(
        g for g in architecturally_covered if g not in hmlr_groups
    )

    print(f"Architecturally covered groups (code is wired to query for these): "
          f"{len(architecturally_covered)}")
    for g in architecturally_covered:
        flag = " [BLOCKED -- HMLR stub, no real Bristol charges until Business Gateway access exists]" if g in hmlr_groups else ""
        print(f"  - {g}{flag}")

    print(f"\nFunctionally covered TODAY for a real Bristol property "
          f"(excludes the 2 HMLR-blocked groups above): {len(functionally_covered_today)}")
    for g in functionally_covered_today:
        print(f"  - {g}")

    print(f"\nSprint 1 success criterion ('at least 10 CON29 question groups for Bristol'):")
    print(f"  Architectural count: {len(architecturally_covered)} "
          f"{'>= 10 -- MET' if len(architecturally_covered) >= 10 else '< 10 -- NOT MET'}")
    print(f"  Functional count (excluding HMLR block): {len(functionally_covered_today)} "
          f"{'>= 10 -- MET' if len(functionally_covered_today) >= 10 else '< 10 -- NOT MET'}")


if __name__ == "__main__":
    main()
