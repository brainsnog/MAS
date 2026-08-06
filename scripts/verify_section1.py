"""
Verifies the sub-question wiring figures in CON29_BUILD_HANDOFF.md Section 1
by deriving them from the registry and the built adapters/agents, rather than
restating a hand-counted claim.

"Architecturally wired" = the dataset's query function maps to a CON29
question ID in CON29_REGISTRY, regardless of whether it currently returns
real data. This includes gis_agent's rights_of_way dataset key, which is
wired (DATASET_TO_QUESTIONS maps it to 2.2-2.5) but always resolves to an
explicit unavailable_reason stub on both boroughs today -- the
graceful-degradation pattern the project mandates, not an absence of wiring.

"Functional" = architecturally wired, minus the IDs that never return real
data today: the HMLR-blocked IDs (3.1, 3.12 -- Business Gateway access
blocked, see hmlr_llc1.py) and the rights-of-way IDs (2.2-2.5 -- always an
unavailable_reason stub on both boroughs, see gis_agent.py).

Run: python3 -m scripts.verify_section1
"""

from src.adapters import historic_england, hmlr_llc1
from src.agents import gis_agent, planning_agent
from src.con29_registry import CON29_REGISTRY


def architecturally_wired_ids() -> set[str]:
    ids: set[str] = set()
    ids.update(hmlr_llc1.COVERS_QUESTIONS)
    ids.update(historic_england.COVERS_QUESTIONS)
    for questions in planning_agent.DATASET_TO_QUESTIONS.values():
        ids.update(questions)
    for questions in gis_agent.DATASET_TO_QUESTIONS.values():
        ids.update(questions)
    registry_ids = {q.question_id for q in CON29_REGISTRY}
    return ids & registry_ids


def functional_ids() -> set[str]:
    registry_ids = {q.question_id for q in CON29_REGISTRY}
    hmlr_ids = set(hmlr_llc1.COVERS_QUESTIONS) & registry_ids
    row_ids = set(gis_agent.DATASET_TO_QUESTIONS["rights_of_way"]) & registry_ids
    return architecturally_wired_ids() - hmlr_ids - row_ids


def main() -> None:
    total = len(CON29_REGISTRY)
    wired = architecturally_wired_ids()
    functional = functional_ids()
    row_ids = set(gis_agent.DATASET_TO_QUESTIONS["rights_of_way"])

    print(f"Architecturally wired: {len(wired)} of {total} ({len(wired) / total:.0%})")
    print(f"  {sorted(wired)}")
    print(f"Functional after HMLR block + rights-of-way stubs: {len(functional)} of {total} ({len(functional) / total:.0%})")
    print(f"  {sorted(functional)}")
    print(f"Rights-of-way IDs (wired to unavailable_reason stubs, not live data): {sorted(row_ids)}")


if __name__ == "__main__":
    main()
