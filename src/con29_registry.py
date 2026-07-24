"""
CON29 question registry.

Source of truth for bucket classification: CON29_ROADMAP_v2.md, "CON29 Field
Classification" section. Do not change bucket assignments here without updating
that section and logging why in Architecture Decisions & Changes.

IMPORTANT — verify before relying on this for anything client-facing:
The `question_text` values below are the roadmap's own group-level descriptions,
not transcribed from the official CON29R form. Where a group covers several
sub-questions (e.g. 1.1a-f), each sub-question currently shares the same
description. The law firm partner holds the actual CON29R form wording —
replace these with the verbatim official question text before Sprint 3
(CON29 Mapper) is built against this registry, since the mapper's output is
meant to be traceable to the real form.

Bucket definitions:
  1 = auto            -> retrieved via API / GIS / open dataset, seconds
  2 = agent_navigated  -> HTML parsing or Playwright fallback, minutes
  3 = manual           -> no automated source; EIR Reg 5(1) request template generated

Some fields are conditional (bucket depends on whether the council happens to
publish the data): these carry both a `bucket` (best-guess default) and a
`conditional_bucket` note.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional

Bucket = Literal["auto", "agent_navigated", "manual"]


@dataclass(frozen=True)
class CON29QuestionDef:
    question_id: str
    question_text: str
    bucket: Bucket
    primary_source: str
    conditional_note: Optional[str] = None


def _expand(prefix: str, letters: str, text: str, bucket: Bucket, source: str,
            conditional_note: Optional[str] = None) -> list[CON29QuestionDef]:
    """Expand a lettered range like ('1.1', 'abcdef', ...) into individual entries."""
    return [
        CON29QuestionDef(
            question_id=f"{prefix}{letter}",
            question_text=text,
            bucket=bucket,
            primary_source=source,
            conditional_note=conditional_note,
        )
        for letter in letters
    ]


CON29_REGISTRY: list[CON29QuestionDef] = [
    # --- Bucket 1: Auto-retrieved (API + open structured data) ---
    *_expand("1.1", "abcdef", "Planning decisions and pending applications",
             "auto", "planning.data.gov.uk API"),
    CON29QuestionDef("1.1g", "Planning enforcement", "auto", "planning.data.gov.uk API"),
    CON29QuestionDef("1.2", "Planning designations (conservation area, AONB)",
                      "auto", "planning.data.gov.uk / GIS"),
    *_expand("2.", "2345", "Public rights of way", "auto", "council GIS layer"),
    CON29QuestionDef("3.1", "Land required for public purposes", "auto",
                      "HMLR LLC1 API (Bristol) / council register"),
    CON29QuestionDef("3.5", "Listed buildings", "auto", "Historic England open data"),
    CON29QuestionDef("3.7", "Tree preservation orders", "auto", "council GIS / open data"),
    *_expand("3.9", "abcdefghijklmn", "Statutory notices and orders",
             "auto", "planning.data.gov.uk API"),
    CON29QuestionDef("3.10", "Community Infrastructure Levy", "auto",
                      "council CIL schedule (downloadable)"),
    CON29QuestionDef("3.11", "Conservation area designation", "auto",
                      "council GIS / planning.data.gov.uk"),
    CON29QuestionDef("3.12", "Compulsory purchase", "auto",
                      "HMLR LLC1 / council register"),
    CON29QuestionDef("3.13", "Contaminated land", "auto", "council open data register"),
    CON29QuestionDef("3.14", "Radon", "auto", "Public Health England API / dataset"),
    CON29QuestionDef("3.15", "Assets of community value", "auto", "council register"),

    # --- Bucket 2: Agent-navigated (HTML parsing or Playwright fallback) ---
    *_expand("1.1", "hi", "Article 4 directions", "agent_navigated",
             "council website (HTML or GIS)"),
    *_expand("1.1", "jkl", "Building regulations (where published)", "agent_navigated",
             "council portal (HTML parsing)",
             conditional_note="Falls to bucket 3 (manual) if not published online — "
                               "email enquiry only"),
    CON29QuestionDef("2.1a", "Highway adoption (where published online)",
                      "agent_navigated", "council / county highways (HTML parsing)",
                      conditional_note="Falls to bucket 3 (manual) where the county/GLA "
                                        "highways authority has no public API"),
    CON29QuestionDef("3.2", "Roadworks / traffic schemes", "agent_navigated",
                      "council portal (HTML if available)"),
    CON29QuestionDef("3.6", "Outstanding notices", "agent_navigated",
                      "council enforcement list (HTML if available)",
                      conditional_note="Falls to bucket 3 (manual) if no online list exists"),

    # --- Bucket 3: Flagged for human follow-up (structurally inaccessible) ---
    *_expand("3.3", "abcdef", "Drainage and sewers", "manual",
             "water authority — separate enquiry"),
    CON29QuestionDef("3.4", "Traffic management schemes", "manual",
                      "physical register at council offices"),
    CON29QuestionDef("3.8", "Noise abatement zones", "manual", "internal council system"),
]


def get_registry() -> list[CON29QuestionDef]:
    return CON29_REGISTRY


def by_bucket(bucket: Bucket) -> list[CON29QuestionDef]:
    return [q for q in CON29_REGISTRY if q.bucket == bucket]


def by_id(question_id: str) -> Optional[CON29QuestionDef]:
    for q in CON29_REGISTRY:
        if q.question_id == question_id:
            return q
    return None


if __name__ == "__main__":
    # Quick sanity check — run with: python -m src.con29_registry
    total = len(CON29_REGISTRY)
    auto = len(by_bucket("auto"))
    agent = len(by_bucket("agent_navigated"))
    manual = len(by_bucket("manual"))
    print(f"Total question entries: {total}")
    print(f"  auto:            {auto} ({auto/total:.0%})")
    print(f"  agent_navigated: {agent} ({agent/total:.0%})")
    print(f"  manual:          {manual} ({manual/total:.0%})")
