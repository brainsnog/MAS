"""
Terminology normalisation lookup tables — pure rules, no LLM, per
CON29_ROADMAP_v2.md Sprint 1 §D.

SCOPE NOTE: Sprint 1's sources (Historic England, planning.data.gov.uk) are
official structured APIs that already return fairly canonical values — HE's
own `grade` field is already "I" / "II*" / "II", not free text like "Grade
Two Star". The genuinely varied "council-specific terminology" problem this
module is aimed at (per the roadmap's own examples — "Grade II Listed" /
"Article 4(1) Restriction") mostly shows up once Sprint 2's HTML-scraped
and PDF-extracted council sources exist, not from Sprint 1's clean APIs.
This module is still built now, for two reasons: (1) Sprint 1's sources DO
occasionally vary in grade formatting in practice, and (2) it gives Sprint 2
a home to extend rather than starting from scratch.
"""

from __future__ import annotations

GRADE_ALIASES: dict[str, str] = {
    "i": "I",
    "grade i": "I",
    "grade 1": "I",
    "grade one": "I",
    "ii*": "II*",
    "ii star": "II*",
    "grade ii*": "II*",
    "grade two star": "II*",
    "grade 2*": "II*",
    "ii": "II",
    "grade ii": "II",
    "grade 2": "II",
    "grade two": "II",
}


def normalise_grade(raw: str | None) -> str | None:
    """
    Map a listed-building grade to its canonical short form (I / II* / II).
    Falls back to the raw (stripped) value if it isn't a recognised alias,
    rather than silently discarding data this module doesn't know how to
    interpret — an unrecognised grade string is still worth keeping on the
    record for a human to see, even if normalisation can't canonicalise it.
    """
    if not raw:
        return None
    key = raw.strip().lower()
    return GRADE_ALIASES.get(key, raw.strip())


# Keyword sets for free-text entity names/descriptions where a dataset
# doesn't already give us a clean boolean. Deliberately conservative
# (substring match, not exact) since council-website free text (Sprint 2)
# is exactly the case this exists for.
ARTICLE_4_KEYWORDS: tuple[str, ...] = ("article 4", "article4", "art 4", "a4 direction")

CONSERVATION_AREA_KEYWORDS: tuple[str, ...] = ("conservation area",)


def mentions_article_4(text: str | None) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(kw in lowered for kw in ARTICLE_4_KEYWORDS)


def mentions_conservation_area(text: str | None) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(kw in lowered for kw in CONSERVATION_AREA_KEYWORDS)
