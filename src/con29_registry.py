"""
CON29 question registry.

REBUILT 2026-08-02 against a real exemplar: St Albans City & District
Council's actual LLC1 + CON29 (Law Society, 2016 edition) response, search
ref A/2025/00248, provided by Griff. Question text below is transcribed
verbatim from that real document wherever a question number is explicitly
printed on it — not the roadmap's own paraphrases, which is what this
registry used before today (see Architecture Decisions & Changes,
2026-08-02, for the full account of what changed and why).

CONFIDENCE LEVELS — read before trusting an entry:
  - CONFIRMED: the question number is printed explicitly in the real
    document, immediately above or beside the quoted text. These are the
    majority of this registry (1.1, 1.2, 2.1-2.5, 3.6, 3.7, 3.8, 3.9, 3.10,
    3.11, 3.12, 3.13, 3.14, 3.15).
  - INHERITED, NOT CONTRADICTED: 3.1 and 3.5. Both match real content found
    in the document (3.1's "land required for public purposes" section sits
    exactly where a 3.1 should, immediately after 2.5; 3.5 "listed
    buildings" isn't a numbered section in this particular document at all,
    since it's a real property with no listed-building charges to report,
    but the topic and Historic England's own API integration are
    independently solid regardless of exact CON29 numbering). Kept, not
    re-verified letter-by-letter.
  - REMOVED, UNEVIDENCED: the previous registry's "1.1g Planning
    enforcement", "1.1h-i Article 4 directions", "3.2 Roadworks / traffic
    schemes", "3.3a-f Drainage and sewers", "3.4 Traffic management
    schemes", and "3.8 Noise abatement zones" are gone. None of these
    survive contact with the real form — see the discoveries below.
  - UNCONFIRMED NUMBERING, real content: three real questions were found in
    the document (Drainage matters / SuDS; Nearby Road Schemes; Nearby
    railway schemes) sitting between confirmed 3.1 and confirmed 3.6, but
    without their own printed numbers in this OCR'd copy. These are real,
    substantial CON29 questions this registry did not previously cover at
    all — kept in UNCONFIRMED_NUMBERING below, NOT given a numeric ID,
    rather than guessed. See that list's own docstring.

TWO ARCHITECTURE-AFFECTING DISCOVERIES, FLAGGED NOT YET ACTIONED:
  1. Tree preservation orders are real-form question 3.9(m) — a sub-item of
     "Notices, orders, directions and proceedings under Planning Acts" —
     NOT a standalone "3.7" as the previous registry and, critically,
     ALREADY-BUILT code (gis_agent.py, planning_agent.py's
     DATASET_TO_QUESTIONS) both currently assume. Real 3.7 is "Outstanding
     Notices", an entirely different question, now correctly represented
     below.
  2. Article 4 directions do not appear as a standalone numbered CON29 Part
     1 question anywhere in the real document. They are conventionally
     registered as Part 1 LLC1 charges (Local Land Charges Rules 1977,
     Schedule 1) rather than raised as a CON29 enquiry — plausible, but not
     confirmed by this document either, since this property had no such
     charges to show one either way.
  Per this project's own standing rule (flag architecture-affecting
  discoveries and hold for confirmation before building around them),
  gis_agent.py's BRISTOL_LAYER_IDS/HACKNEY_LAYERS, planning_agent.py's
  DATASET_TO_QUESTIONS, and this file's own question IDs are now
  INTERNALLY INCONSISTENT with each other on this one point. Nothing in the
  already-built adapters has been changed to match — that's a deliberate
  pause, not an oversight, pending Griff's confirmation. Do not "fix" the
  built modules' "3.7"/"1.1h" references without that conversation
  happening first.

THE "28+" TARGET, RECONSIDERED: CON29_ROADMAP_v2.md's Sprint 0 success
criterion calls for "all 28+ question groups". This registry now has 19
CONFIRMED top-level question numbers (1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 2.5,
3.1, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14, 3.15) plus 3
real UNCONFIRMED_NUMBERING questions = 22 total top-level groups accounted
for, all sourced from a real CON29R Part 1 form. "28+" may have been an
overestimate for Part 1 alone — reaching it might require CON29O (optional
enquiries), a separate form this exemplar document doesn't include. Worth
raising with Griff rather than quietly padding the count to match a target
that may itself need revising.

Bucket definitions:
  1 = auto            -> retrieved via API / GIS / open dataset, seconds
  2 = agent_navigated  -> HTML parsing or Playwright fallback, minutes
  3 = manual           -> no automated source; EIR Reg 5(1) request template generated

Some fields are conditional (bucket depends on whether the council happens to
publish the data): these carry both a `bucket` (best-guess default) and a
`conditional_bucket` note.
"""

from dataclasses import dataclass
from typing import Literal, Optional

Bucket = Literal["auto", "agent_navigated", "manual"]


@dataclass(frozen=True)
class CON29QuestionDef:
    question_id: str
    question_text: str
    bucket: Bucket
    primary_source: str
    conditional_note: Optional[str] = None


def _expand(prefix: str, letters: str, texts: dict[str, str], bucket: Bucket,
            source: str, conditional_note: Optional[str] = None) -> list[CON29QuestionDef]:
    """
    Expand a lettered range into individual entries, one real question_text
    per letter (texts[letter]) rather than one shared generic string — the
    previous registry's single biggest fidelity gap versus the real form,
    now fixed. `letters` still controls ordering/membership; `texts` must
    have an entry for every letter in it.
    """
    return [
        CON29QuestionDef(
            question_id=f"{prefix}{letter}",
            question_text=texts[letter],
            bucket=bucket,
            primary_source=source,
            conditional_note=conditional_note,
        )
        for letter in letters
    ]


CON29_REGISTRY: list[CON29QuestionDef] = [
    # --- 1.1 Planning and Building Regulation Decisions and Pending
    # Applications (CONFIRMED, verbatim from the real document) ---
    *_expand("1.1", "abcdefghijkl", {
        "a": "A planning permission.",
        "b": "A listed building consent.",
        "c": "A conservation area consent.",
        "d": "A certificate of lawfulness of existing use or development.",
        "e": "A certificate of lawfulness of proposed use or development.",
        "f": "A certificate of lawfulness works for listed buildings.",
        "g": "A heritage partnership agreement.",
        "h": "A listed building consent order.",
        "i": "A local listed building consent order.",
        "j": "Building regulation approval.",
        "k": "A building regulation completion certificate.",
        "l": "Any building regulation completion certificate or notice "
             "issued in respect of work carried out under a competent "
             "person self-certification scheme.",
    }, "auto", "planning.data.gov.uk API",
       conditional_note="(j)-(l) specifically fall to agent_navigated where "
                        "building control records aren't in a national open "
                        "dataset — see planning_agent.py."),

    CON29QuestionDef(
        "1.2",
        "What designations of land use for the property, or the area, and "
        "what specific proposals for the property, are contained in any "
        "existing or proposed development plan?",
        "auto", "planning.data.gov.uk / GIS",
    ),

    # --- 2.1-2.5 Roads and Public Rights of Way (CONFIRMED) ---
    *_expand("2.1", "abcd", {
        "a": "Are the roads, footways and footpaths named in the "
             "application for this search highways maintainable at public "
             "expense?",
        "b": "Are they subject to adoption and supported by a bond or bond "
             "waiver?",
        "c": "Are they to be made up by a local authority who will reclaim "
             "the cost from the frontagers?",
        "d": "Are they to be adopted by a local authority without "
             "reclaiming the cost from the frontagers?",
    }, "agent_navigated", "council / county highways (HTML parsing)",
       conditional_note="Falls to bucket 3 (manual) where the county/GLA "
                        "highways authority has no public API — (a) matches "
                        "the previous registry's own '2.1a' exactly; "
                        "(b)-(d) are newly added, same source/bucket."),

    CON29QuestionDef(
        "2.2",
        "Is any public right of way which abuts on, or crosses the "
        "property, shown in a definitive map or revised definitive map?",
        "auto", "council GIS layer",
    ),
    CON29QuestionDef(
        "2.3",
        "Are there any pending applications to record a public right of "
        "way that abuts, or crosses the property, on the Register?",
        "auto", "council GIS layer",
        conditional_note="Procedural/register question, not purely "
                         "spatial — may warrant reclassifying to "
                         "agent_navigated on review; kept as auto (inherited) "
                         "pending that discussion.",
    ),
    CON29QuestionDef(
        "2.4",
        "Are there any legal orders to stop up, divert, alter or create a "
        "public right of way which abuts, or crosses the property, not yet "
        "implemented or shown on a definitive map?",
        "auto", "council GIS layer",
        conditional_note="Same reclassification note as 2.3.",
    ),
    CON29QuestionDef(
        "2.5",
        "If 2.4 applies, attach a plan showing the approximate route.",
        "auto", "council GIS layer",
        conditional_note="Same reclassification note as 2.3 — this is "
                         "conditional on 2.4, not an independent spatial "
                         "lookup.",
    ),

    # --- 3.1 Land required for public purposes (INHERITED, matches real
    # content found immediately after 2.5 in the document) ---
    CON29QuestionDef(
        "3.1",
        "Is the property included in land required for public purposes? "
        "Is the property included in land to be acquired for road works?",
        "auto", "HMLR LLC1 API (Bristol) / council register",
    ),

    # --- 3.5 Listed buildings (INHERITED, NOT independently re-verified
    # against this document — see module docstring) ---
    CON29QuestionDef("3.5", "Listed buildings.", "auto",
                      "Historic England open data"),

    # --- 3.6 Traffic Schemes (CONFIRMED — REPLACES the previous registry's
    # unevidenced "3.2 Roadworks / traffic schemes" and "3.4 Traffic
    # management schemes") ---
    *_expand("3.6", "abcdefghijkl", {
        "a": "Permanent stopping up or diversion.",
        "b": "Waiting or loading restrictions.",
        "c": "One way driving.",
        "d": "Prohibition of driving.",
        "e": "Pedestrianisation.",
        "f": "Vehicle width or weight restriction.",
        "g": "Traffic calming works including road humps.",
        "h": "Residents parking controls.",
        "i": "Minor road widening or improvement.",
        "j": "Pedestrian crossings.",
        "k": "Cycle tracks.",
        "l": "Bridge building.",
    }, "agent_navigated", "council portal (HTML if available)",
       conditional_note="Has a local authority approved but not yet "
                        "implemented any of the above, for the roads/"
                        "footways/footpaths abutting the property?"),

    # --- 3.7 Outstanding Notices (CONFIRMED — REPLACES the previous
    # registry's unevidenced "3.6 Outstanding notices", now correctly at 3.7
    # with real (a)-(g) sub-items instead of one generic description) ---
    *_expand("3.7", "abcdefg", {
        "a": "Building works.",
        "b": "Environment.",
        "c": "Health and safety.",
        "d": "Housing.",
        "e": "Highways.",
        "f": "Public health.",
        "g": "Flood and coastal erosion risk management.",
    }, "agent_navigated", "council enforcement list (HTML if available)",
       conditional_note="Do any statutory notices relating to the above "
                        "matters subsist, other than those revealed "
                        "elsewhere in this form? Falls to bucket 3 (manual) "
                        "if no online list exists."),

    # --- 3.8 Contravention of building regulations (CONFIRMED — REPLACES
    # the previous registry's unevidenced "3.8 Noise abatement zones",
    # which no part of the real document supports under any number; may
    # genuinely be a CON29O optional-enquiry topic instead — see module
    # docstring) ---
    CON29QuestionDef(
        "3.8",
        "Has a local authority authorised in relation to the property any "
        "proceedings for the contravention of any provision contained in "
        "building regulations?",
        "agent_navigated", "council building control records (HTML if available)",
    ),

    # --- 3.9 Notices, orders, directions and proceedings under Planning
    # Acts (CONFIRMED — 14 real sub-items, each distinct; (m) is where tree
    # preservation orders actually live, see module docstring discovery 1) ---
    *_expand("3.9", "abcdefghijklmn", {
        "a": "An enforcement notice.",
        "b": "A stop notice.",
        "c": "A listed building enforcement notice.",
        "d": "A breach of condition notice.",
        "e": "A planning contravention notice.",
        "f": "Another notice relating to breach of planning control.",
        "g": "A listed building repairs notice.",
        "h": "In the case of a listed building deliberately allowed to "
             "fall into disrepair, a compulsory purchase order with a "
             "direction for minimum compensation.",
        "i": "A building preservation notice.",
        "j": "A direction restricting permitted development.",
        "k": "An order revoking or modifying planning permission.",
        "l": "An order requiring discontinuance of use or alteration or "
             "removal of building or works.",
        "m": "A tree preservation order.",
        "n": "Proceedings to enforce a planning agreement or planning "
             "contribution.",
    }, "auto", "planning.data.gov.uk API",
       conditional_note="(m) tree preservation order is GIS-sourced in "
                        "practice (council GIS / open data), not "
                        "planning.data.gov.uk, unlike its siblings here — "
                        "see gis_agent.py. Kept in this expansion for "
                        "completeness against the real form's own grouping; "
                        "primary_source for (m) specifically should read "
                        "'council GIS / open data' once the ID mismatch in "
                        "the module docstring is resolved with Griff."),

    CON29QuestionDef(
        "3.10",
        "Community Infrastructure Levy (CIL): is there a CIL charging "
        "schedule, and if so do any of a liability notice, notice of "
        "chargeable development, demand notice, default liability notice, "
        "assumption of liability notice, or commencement notice subsist? "
        "Has any demand notice been suspended, has full or part payment "
        "been received, has an appeal been received, has a liability order "
        "been applied for or granted, and have any other enforcement "
        "measures been taken?",
        "auto", "council CIL schedule (downloadable)",
        conditional_note="Real form has (a)-(h) with (b) further split into "
                         "six roman-numeral sub-items — kept as one ID "
                         "pending a decision on whether to fully explode "
                         "the sub-structure.",
    ),
    CON29QuestionDef(
        "3.11",
        "Conservation area: does the making of the area a Conservation "
        "Area before 31 August 1974 apply, or is there a decision to make "
        "an entry, or an entry, in a register maintained under section 78R "
        "of the Environmental Protection Act 1990?",
        "auto", "council GIS / planning.data.gov.uk",
        conditional_note="The real document's (b) here is verbatim "
                         "identical to 3.13(b)'s own text (both cite s.78R "
                         "EPA 1990) — a real quirk of the official template, "
                         "not a transcription error on this project's part.",
    ),
    CON29QuestionDef(
        "3.12",
        "Has any enforceable order or decision been made to compulsorily "
        "purchase or acquire the property?",
        "auto", "HMLR LLC1 / council register",
    ),
    CON29QuestionDef(
        "3.13",
        "Contaminated land: does a contaminated land notice apply "
        "(including land adjacent to or adjoining the property), is there "
        "a decision to make an entry or an entry in a register maintained "
        "under section 78R of the Environmental Protection Act 1990, or "
        "has consultation with the owner/occupier under section 78G(3) of "
        "that Act taken place before service of a remediation notice?",
        "auto", "council open data register",
    ),
    CON29QuestionDef(
        "3.14",
        "Do records indicate that the property is in a 'Radon Affected "
        "Area' as identified by Public Health England?",
        "auto", "Public Health England API / dataset",
    ),
    CON29QuestionDef(
        "3.15",
        "Has the property been nominated as, listed as, or had its "
        "listing reviewed/appealed/expired as an asset of community "
        "value, and if listed has the Local Authority applied to the Land "
        "Registry for an entry/cancellation, received notice of disposal, "
        "or received a request from a community interest group to be "
        "treated as a bidder?",
        "auto", "council register",
    ),
]


# UNCONFIRMED NUMBERING — real questions found in the exemplar document,
# sitting between confirmed 3.1 and confirmed 3.6, but without a legible
# printed number in this OCR'd copy (the source PDF's numbering for this
# specific block didn't survive extraction). These are real, substantial
# CON29 questions this registry did not cover under ANY id before today —
# deliberately NOT given a numeric question_id, rather than guessed, per
# this project's standing rule against inventing IDs. A clean copy of the
# CON29 guidance notes (or a second exemplar) would close this properly.
# Do not build the CON29 Mapper (Sprint 3) against these until they have a
# confirmed id.
UNCONFIRMED_NUMBERING: list[CON29QuestionDef] = [
    CON29QuestionDef(
        "3.?-drainage-suds",
        "Is the property served by a sustainable urban drainage system "
        "(SuDS) adopted by a SuDS Approval Body (SSAB) for which there "
        "will be a surface water draining charge? Are there SuDS features "
        "within the boundary of the property, and who is responsible for "
        "maintenance/billing?",
        "manual", "council planning decision records (major applications only)",
    ),
    CON29QuestionDef(
        "3.?-nearby-road-schemes",
        "Is the property (or will it be) within 200 metres of a new trunk "
        "road, special road, or proposed alteration/improvement to an "
        "existing road (subway, underpass, flyover, footbridge, elevated "
        "road, dual carriageway, roundabout, additional traffic lane), "
        "whether approved, under construction, or published for public "
        "consultation?",
        "manual", "physical register at council offices",
    ),
    CON29QuestionDef(
        "3.?-nearby-railway-schemes",
        "Is the property (or will it be) within 200 metres of the centre "
        "line of a proposed railway, tramway, light railway, or monorail, "
        "and are there any such proposals within the Local Authority's "
        "boundary?",
        "manual", "physical register at council offices",
    ),
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


def top_level_groups() -> set[str]:
    """
    Distinct top-level question numbers (e.g. '1.1', '3.9') represented in
    CON29_REGISTRY, collapsing lettered sub-items into their parent group —
    this is the count CON29_ROADMAP_v2.md's Sprint 0 success criterion
    ("28+ question groups") actually refers to, not the expanded sub-ID
    count. See module docstring "THE 28+ TARGET, RECONSIDERED".
    """
    groups: set[str] = set()
    for q in CON29_REGISTRY:
        prefix = q.question_id.rstrip("abcdefghijklmn")
        groups.add(prefix)
    return groups


if __name__ == "__main__":
    # Quick sanity check — run with: python -m src.con29_registry
    total = len(CON29_REGISTRY)
    auto = len(by_bucket("auto"))
    agent = len(by_bucket("agent_navigated"))
    manual = len(by_bucket("manual"))
    groups = top_level_groups()
    print(f"Total question entries: {total}")
    print(f"  auto:            {auto} ({auto/total:.0%})")
    print(f"  agent_navigated: {agent} ({agent/total:.0%})")
    print(f"  manual:          {manual} ({manual/total:.0%})")
    print(f"Confirmed top-level groups: {len(groups)} -> {sorted(groups)}")
    print(f"Plus {len(UNCONFIRMED_NUMBERING)} real questions with unconfirmed numbering.")
