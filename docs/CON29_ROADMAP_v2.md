# CON29 Automated Search — Multi-Agent System
## 30-Day Project Roadmap, PRD & Living Context Document
### Version 2.0 — Revised Architecture

---

> ## INSTRUCTION FOR ALL CLAUDE INSTANCES READING THIS FILE
>
> **Read this entire document before writing a single line of code, creating any file, or making any architectural decision.** This document is the product of weeks of research, literature review, system design discussion, and deliberate architectural pivots. Nothing in here is accidental.
>
> ### Your responsibilities after every work session:
> - Check off completed tasks with `[x]`
> - Update the **Current State** block at the top
> - Add a dated entry to the **Project Log**
> - Record any architecture changes in **Architecture Decisions & Changes**
> - Record any bugs or unexpected behaviour in **Troubleshooting Log**
>
> ### Non-negotiable rules:
> - Do not start a new sprint until the previous sprint's success criteria are all checked off
> - Do not change the architecture without recording why in the decisions log
> - Do not add LLM calls where deterministic code can do the same job
> - Do not use Playwright unless all structured source options have been exhausted for a field
> - The end goal is a working, evaluated, demo-able proof of concept — not a perfect system

---

## Current State

```
Version:       2.0 (major architecture revision from v1.0)
Phase:         IN PROGRESS
Last updated:  2026-08-03
Active sprint: Sprint 2 — GIS Agent & Document Agent. GIS Agent (§A) built and
               tested. Document Agent (§B: pdf_extractor.py, llm_extractor.py)
               and session_store.py not yet started. Test property set (§C)
               not yet locked. con29_registry.py rebuilt against a real
               exemplar (out-of-band with §A/§B/§C, see below) — required
               reading before Sprint 3's CON29 Mapper starts.
Blockers:      HMLR LLC1 access — Business Gateway requires an active Business
               e-services account (Basic Auth), not a self-serve API key. No
               public "developer.hmlr.gov.uk" signup exists. Likely resolution
               path: law firm partner's existing Business Gateway account, or
               direct contact via channelpartners@landregistry.gov.uk. Affects
               Bristol LLC1 charges only (Hackney LLC1 fields are already
               coverage_flag: manual per the Borough B design). Does not block
               Sprint 2 — src/adapters/hmlr_llc1.py's graceful-degradation
               stub stays in place until this is resolved.
Next action:   **con29_registry.py rebuilt 2026-08-02** against a real St
               Albans CON29R/LLC1 exemplar Griff shared (search ref
               A/2025/00248) — verbatim official question text throughout,
               replacing this roadmap's own paraphrases. 63 sub-question
               entries across 19 confirmed top-level groups, plus 3 real
               questions (SuDS/drainage, nearby road schemes, nearby railway
               schemes) held in a separate UNCONFIRMED_NUMBERING list rather
               than given a guessed question number. See Architecture
               Decisions & Changes for the full account.

               **ARCHITECTURE-AFFECTING DISCOVERY — RESOLVED 2026-08-03:**
               the real form puts tree preservation orders at 3.9(m), not a
               standalone "3.7" (real 3.7 is "Outstanding Notices"). Article
               4 directions have no standalone CON29 Part 1 question number
               in the real form at all (plausibly LLC1-register-sourced
               instead — Part 1 LLC1 charge under the Local Land Charges
               Rules 1977). Both `gis_agent.py` and `planning_agent.py`
               have now been corrected to match: TPO references changed
               "3.7" -> "3.9m"; Article 4 moved out of each module's
               `DATASET_TO_QUESTIONS` into a new `NON_CON29_DATASETS` dict
               (still queried — real, useful evidence-manifest data — just
               no longer claimed to answer a CON29 question). Enforcement
               notices, previously mis-mapped to "1.1g", are now correctly
               "3.9a"; real 1.1g ("a heritage partnership agreement") is
               left honestly uncovered rather than force-mapped to a
               dataset that doesn't really answer it.

               `planning_agent.py`'s query loop was iterating
               `DATASET_TO_QUESTIONS` directly to decide what to fetch —
               moving Article 4 out of that dict would have silently
               stopped querying it. Fixed by introducing `ALL_DATASETS`
               (the union of `DATASET_TO_QUESTIONS` and
               `NON_CON29_DATASETS`) and querying that instead, so Article
               4 data keeps flowing. `gis_agent.py` was already safe here —
               its query calls are hardcoded per-dataset, not
               dict-iteration-driven.

               **A REAL, HONEST REGRESSION SURFACED BY THIS FIX:**
               `scripts/tally_sprint1_coverage.py`'s own hardcoded group
               table had the same wrong IDs baked in (a standalone "3.7"
               group, "1.1h-i Article 4", a mislabeled "3.6 Outstanding
               notices", a nonexistent "3.2"). Correcting them drops the
               tally from 10 architectural / 8 functional groups to 8 / 6 —
               Sprint 1's own "at least 10 groups" success criterion,
               reported met at Sprint 1's closure, **is no longer met** with
               the corrected IDs. This is not a loss of functionality — the
               same adapters make the same real API calls either way — it's
               a correction to what those calls were honestly claimed to
               answer. Flagged here and in Architecture Decisions rather
               than silently patched to keep the old claim looking true.
               Worth a direct conversation with Griff about whether Sprint
               1's closure needs revisiting, separate from continuing
               Sprint 2.

               Also reassessed: the roadmap's own "28+ question groups"
               Sprint 0 target may have been an overestimate for CON29 Part
               1 alone — the real form's Part 1 tops out around 19-22
               top-level groups; reaching "28+" might require CON29O
               (optional enquiries), a separate form this exemplar doesn't
               include.

               DescribeFeatureType schema call (for the Hackney
               HACKNEY_GEOM_FIELD gap flagged last session) returned only a
               wrapper document with two unfollowed `xsd:import`s — real,
               but inconclusive. Two follow-up URLs given to Griff; gap
               stays open. Two remaining concrete API-fixture moves
               (Historic England `/query` body, a first Gemini/Groq call)
               deferred by mutual agreement to continue with the rest of
               Sprint 2 first.

               NEXT: Sprint 2 §B — Document Agent (pdf_extractor.py using
               PyMuPDF, llm_extractor.py — the first real Gemini call this
               project makes) and §C's session_store.py. Test property set
               (§C) still needs locking with the law firm partner before
               Sprint 3 — a hard gate per this roadmap's own rules, do not
               proceed past it without that confirmation.
```

---

## What Changed From v1.0 and Why

This is version 2.0 of the roadmap. The original (v1.0) proposed LangGraph as the primary
orchestrator, Playwright as the primary retrieval method for Borough B, and a cellular RAG loop
as the main extraction architecture. All three of those choices have been revised.

| What changed | Old approach | New approach | Reason |
|---|---|---|---|
| Primary orchestrator | LangGraph state machine | Plain Python orchestrator | LangGraph is overkill for a linear pipeline; adds complexity without benefit at this scale |
| Primary retrieval | Playwright browser automation | Official APIs → GIS → open data → HTML → Playwright (last resort) | Reliability hierarchy produces higher-confidence outputs; Playwright is brittle and hard to maintain |
| Extraction architecture | Cellular RAG loop on all portal HTML | LLM only where deterministic methods fail (PDFs, unstructured text) | 80% of CON29-relevant data is available from structured sources without any LLM |
| Borough B | Mole Valley District Council | London Borough of Hackney | Lawyer partner direct experience; Hackney cyberattack (2020, recovery ongoing) is a documented real-world case of legacy system failure |
| Demo format | CLI script | Gradio UI on Hugging Face Spaces | Examiners can click a link; demonstrates a real system |
| LLM role | Central to all extraction | Narrow: PDF extraction, terminology normalisation, conflict detection | More academically defensible; most of the pipeline is data engineering, not AI |

---

## The End Goal — Read This Every Session

We are building a **proof-of-concept automated CON29 personal search system** that demonstrates:

1. A property address can be resolved to a UPRN and spatial polygon automatically
2. The majority of CON29-relevant data can be retrieved from structured, authoritative sources without human intervention
3. Where structured sources exist, retrieval is near-instant (seconds, not days)
4. Where only unstructured documents exist (PDFs, committee reports), a small LLM call extracts the relevant fields
5. Where no automated source exists, the system correctly classifies the field as requiring human follow-up
6. Every answer is traceable to an exact source, URL, timestamp, and document — an evidence manifest
7. The system performs demonstrably differently across two borough archetypes (Bristol vs Hackney), quantifying the gap that digital maturity creates

**What this system is NOT:**
- A legally signed search result
- A replacement for a qualified conveyancer
- Generalisable to all UK authorities (it proves the concept on two)
- AI-generating answers — it retrieves answers from authoritative sources and maps them to CON29 fields

**The key academic distinction** (state this clearly in the dissertation):
> "This system does not use AI to infer or generate conveyancing answers. It uses AI agents to orchestrate retrieval from authoritative public sources and to extract structured data from unstructured documents where rules-based parsing is insufficient. Every output is traceable to a named source."

This distinction matters to insurers, underwriters, regulators, and examiners alike.

---

## System Architecture — Canonical Version

Every component below is deliberate. Do not change anything without recording why.

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INPUT                                │
│            Property address (free text)                      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              PROPERTY RESOLVER                               │
│  Address → UPRN → Coordinates → Boundary Polygon             │
│  Sources: OS Names API, planning.data.gov.uk /entity         │
│  Output: uprn, lat/lon, WKT polygon, local_authority_code    │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              RETRIEVAL ORCHESTRATOR                          │
│         (Plain Python — async parallel dispatch)             │
│                                                              │
│  For each CON29 field, attempt sources in this order:        │
│  1. Official REST API         → confidence: HIGH             │
│  2. Official GIS (ArcGIS/WFS) → confidence: HIGH            │
│  3. Downloadable dataset      → confidence: HIGH             │
│  4. National cached dataset   → confidence: HIGH             │
│  5. Structured JSON (hidden)  → confidence: MEDIUM           │
│  6. HTML parsing              → confidence: MEDIUM           │
│  7. Playwright automation     → confidence: LOW (last resort)│
│  8. Flag for human follow-up  → coverage_flag: MANUAL        │
└──────┬──────────────┬──────────────┬───────────────────────-┘
       │              │              │
       ▼              ▼              ▼
┌──────────┐   ┌──────────┐   ┌──────────────────────────────┐
│ PLANNING │   │   GIS    │   │    DOCUMENT RETRIEVAL        │
│  AGENT   │   │  AGENT   │   │         AGENT                │
│          │   │          │   │                              │
│ planning.│   │ ArcGIS   │   │ Downloads PDFs, HTML pages   │
│ data.gov │   │ WFS/WMS  │   │ decision notices, committee  │
│ HMLR API │   │ Historic │   │ reports, enforcement notices │
│ Council  │   │ England  │   │                              │
│ planning │   │ Env Agcy │   │ Stores in ephemeral session  │
│ register │   │ GIS      │   │ folder during search         │
└──────┬───┘   └─────┬────┘   └──────────────┬───────────────┘
       │              │                        │
       ▼              ▼                        ▼
┌─────────────────────────────────────────────────────────────┐
│                 RAW EVIDENCE STORE                           │
│            (ephemeral, per search_id folder)                 │
│  /searches/{search_id}/raw/   → PDFs, HTML, JSON, GIS       │
│  /searches/{search_id}/meta/  → source URLs, timestamps     │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              NORMALISATION LAYER                             │
│          (deterministic rules — no LLM)                      │
│                                                              │
│  Maps council-specific terminology to canonical CON29 schema │
│  e.g. "Grade II Listed" → listed_building: true             │
│  e.g. "Article 4(1) Restriction" → article_4: true          │
│  Structured API/GIS outputs → PropertyRecord fields          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              LLM EXTRACTION LAYER                            │
│        (Gemini 2.5 Flash — only where needed)                │
│                                                              │
│  Triggered only for:                                         │
│  - PDFs (decision notices, enforcement notices, reports)     │
│  - Unstructured HTML that normalisation cannot parse         │
│  - Terminology conflicts between sources                     │
│                                                              │
│  Input: relevant text sections only (not whole documents)    │
│  Output: structured JSON field values + exact quote cited    │
│  Calls: 1 normally, 2 max for complex/conflicting cases      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              CON29 MAPPER                                    │
│          (deterministic rules — no LLM)                      │
│                                                              │
│  Maps canonical PropertyRecord fields → CON29 question IDs  │
│  Assigns coverage_flag per field                             │
│  Assigns confidence_score per field based on source tier     │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              VALIDATION AGENT                                │
│                                                              │
│  Cross-checks answers across sources                         │
│  e.g. if API says conservation_area=False but GIS says True  │
│  → flags CONFLICT, recommends manual review                  │
│  LLM used only for conflict interpretation                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    OUTPUTS                                   │
│                                                              │
│  1. CON29 JSON Schema (structured field answers)             │
│  2. Evidence Manifest (source, URL, timestamp, citation)     │
│  3. PDF Report (human-readable, downloadable)                │
│  4. Coverage Summary (auto/manual/unavailable per field)     │
│                                                              │
│  Session cleanup: raw PDFs deleted after report generated    │
│  Retained: JSON output, evidence manifest, evaluation log    │
└─────────────────────────────────────────────────────────────┘
```

---

## CON29 Field Classification

This is the definitive classification of which fields the system attempts to retrieve
and how. Do not change this without consulting the law firm partner.

### Bucket 1 — Auto-retrieved (API + open structured data, seconds)
Target: ~55–60% of CON29R question groups

| CON29 Question | Description | Primary Source |
|---|---|---|
| 1.1a–f | Planning decisions and pending applications | planning.data.gov.uk API |
| 1.1g | Planning enforcement | planning.data.gov.uk API |
| 1.2 | Planning designations (conservation area, AONB) | planning.data.gov.uk / GIS |
| 2.2–2.5 | Public rights of way | council GIS layer |
| 3.1 | Land required for public purposes | HMLR LLC1 API (Bristol) / council register |
| 3.5 | Listed buildings | Historic England API |
| 3.7 | Tree preservation orders | council GIS / open data |
| 3.9a–n | Statutory notices and orders | planning.data.gov.uk API |
| 3.10 | Community Infrastructure Levy | council CIL schedule (downloadable) |
| 3.11 | Conservation area designation | council GIS / planning.data.gov.uk |
| 3.12 | Compulsory purchase | HMLR LLC1 / council register |
| 3.13 | Contaminated land | council open data register |
| 3.14 | Radon | Public Health England API / dataset |
| 3.15 | Assets of community value | council register |

### Bucket 2 — Agent-navigated (HTML parsing or Playwright fallback, minutes)
Target: ~15–20% of CON29R question groups

| CON29 Question | Description | Source | Method |
|---|---|---|---|
| 1.1h–i | Article 4 directions | council website | HTML or GIS |
| 1.1j–l | Building regulations (where published) | council portal | HTML parsing |
| 2.1a | Highway adoption (where published online) | council / county highways | HTML parsing |
| 3.2 | Roadworks / traffic schemes | council portal | HTML if available |
| 3.6 | Outstanding notices | council enforcement list | HTML if available |

### Bucket 3 — Flagged for human follow-up (structural inaccessibility)
Target: ~25% of CON29R question groups

| CON29 Question | Description | Why inaccessible |
|---|---|---|
| 1.1j–l | Building regulations (if not published) | Email enquiry only |
| 2.1a | Highway adoption (if county only) | Surrey/GLA highways authority — no public API |
| 3.3a–f | Drainage and sewers | Water authority — separate enquiry |
| 3.4, 3.6 | Traffic management schemes | Physical register at council offices |
| 3.8 | Noise abatement zones | Internal council system |

For every Bucket 3 field the system generates a pre-populated EIR/FOI request template
identifying the specific data required and the relevant regulation (EIR Reg 5(1)).
A human dispatches the request. The system does not auto-send.

---

## Source Reliability Hierarchy

Every field answer is assigned a confidence score based on its source.
This score is stored in the evidence manifest and displayed in the UI.

| Tier | Source type | Confidence | Examples |
|---|---|---|---|
| 1 | Official REST API | HIGH | HMLR LLC1, planning.data.gov.uk, Historic England |
| 1 | Official GIS service (ArcGIS REST, WFS, WMS) | HIGH | Council ArcGIS, OS MasterMap |
| 2 | Downloadable structured dataset | HIGH | GeoJSON, CSV, shapefile from data.gov.uk |
| 2 | National cached dataset | HIGH | Historic England listed buildings dataset |
| 3 | Structured JSON hidden behind web page | MEDIUM | Council portal API endpoints |
| 4 | HTML parsing (structured) | MEDIUM | Well-structured council register pages |
| 5 | PDF extraction via LLM | MEDIUM-LOW | Decision notices, enforcement notices |
| 6 | Browser automation (Playwright) | LOW | Last resort for legacy portals |
| — | No automated source found | MANUAL | Bucket 3 fields |

---

## The Two Borough Case Studies

### Borough A — Bristol City Council (High Digital Maturity)

**Why Bristol:**
- HMLR LLC1-migrated (July 2023, Gold status)
- Planning data available via planning.data.gov.uk API with polygon queries
- High geometric integrity — data anchored to spatial polygons, not text strings
- Enables programmatic property boundary queries (WKT polygon → planning results)
- Contrast: represents the ceiling of what current UK digitisation enables

**What the system achieves for Bristol:**
- LLC1 data via HMLR REST API → instant
- Planning history, enforcement, designations via planning.data.gov.uk → instant
- Listed buildings via Historic England API → instant
- TPOs, conservation areas via Bristol open GIS data → instant
- Remaining fields (highways, building regs, drainage) → Bucket 3, flagged

**Borough A coverage target:** ~65% of CON29 fields auto-retrieved

### Borough B — London Borough of Hackney (Low Digital Maturity)

**Why Hackney:**
- Not yet migrated to HMLR LLC1 as of June 2026
- Suffered a significant cyberattack in 2020; land charges system affected, partial
  recovery ongoing as of February 2026 — running degraded partial search service
- Text-anchored data (address strings, not spatial polygons) in legacy systems
- Law firm partner has direct experience with retrieval failures from Hackney
- Contrast: represents the floor — the worst-case scenario that motivates the project

**What the system achieves for Hackney:**
- Planning history via Hackney planning register (structured HTML / hidden JSON)
- Listed buildings via Historic England API (same national source as Bristol)
- TPOs via Hackney open data (weekly GIS exports where available)
- Conservation areas via planning.data.gov.uk (partially migrated data)
- LLC1 data: council's own register — HTML parsing or Playwright fallback
- More fields fall to Bucket 3 compared to Bristol

**Borough B coverage target:** ~40–45% of CON29 fields auto-retrieved

**Why the gap matters academically:**
The difference in auto-retrieval coverage between Bristol (~65%) and Hackney (~40%)
is the dissertation's primary quantitative finding. It directly measures the cost
of digital immaturity in terms of automatable search coverage.

---

## The LLM Model Comparison Experiment

This turns the model selection decision into a methodology contribution.

**Experiment design:**
- Collect 20 real planning documents (decision notices, enforcement notices,
  committee reports) from both boroughs
- Run the same extraction prompts against three models:
  1. Gemini 2.5 Flash (primary candidate)
  2. Qwen 3 8B via Groq API (open-weight candidate)
  3. Llama 3.1 8B via Groq API (baseline open-weight)
- Measure: extraction accuracy, JSON validity rate, latency, cost per document
- Ground truth: manually annotated field values for all 20 documents

**Why this strengthens the dissertation:**
Model selection becomes a research finding rather than an implementation decision.
The experiment provides empirical justification for whichever model performs best
and gives the dissertation a quantitative methodology section.

**Expected outcome:** Gemini 2.5 Flash wins on JSON validity and accuracy.
Groq-hosted models win on latency. Document this as a cost/accuracy trade-off finding.

---

## Tech Stack

```
Language:           Python 3.11+
Orchestration:      Plain Python (asyncio) — LangGraph not used at MVP stage
HTTP clients:       httpx (async), requests (sync fallback)
GIS queries:        geopandas, shapely, pyproj
PDF extraction:     PyMuPDF (fitz) — faster and more reliable than pdfplumber for UK docs
HTML parsing:       BeautifulSoup4 + lxml
LLM:                google-generativeai (Gemini 2.5 Flash primary)
LLM comparison:     Groq API (Qwen 3 8B, Llama 3.1 8B) — model eval experiment only
Schema validation:  Pydantic v2 strict mode
PDF report gen:     ReportLab or WeasyPrint
Demo UI:            Gradio (hosted on Hugging Face Spaces)
Storage:            Local filesystem during dev; HF Spaces persistent storage for demo
Database:           SQLite (evaluation logs only — no operational database needed)
Testing:            pytest + pytest-asyncio
Environment:        python-dotenv
Version control:    Git (GitHub)
```

**API keys required (never commit):**
```
GOOGLE_API_KEY=          # Gemini — Google AI Studio (free tier sufficient)
GROQ_API_KEY=            # Groq — free tier (model eval experiment only)
HMLR_BG_USERNAME=        # HMLR Business Gateway — Basic Auth, NOT a self-serve key.
HMLR_BG_PASSWORD=        # Requires an active Business e-services account. BLOCKED
                         # as of 2026-07-22 — see Current State / Troubleshooting Log.
OS_PLACES_API_KEY=       # OS Places API (DPA dataset) — resolves address -> UPRN + coords.
                         # osdatahub.os.uk — add "Places API" product to existing account.
                         # NOTE: OS Names API (already registered) is a place-name gazetteer
                         # only; it cannot return a UPRN for a specific address. Keep the
                         # Names key too in case gazetteer lookups are useful elsewhere, but
                         # it does not satisfy the property resolver's job.
OS_NAMES_API_KEY=        # Already registered — gazetteer/place-name search only, not used
                         # for UPRN resolution
# HISTORIC_ENGLAND_KEY=  # Likely NOT required — NHLE listed buildings / conservation
                         # area data is published as open data (ArcGIS REST / WFS,
                         # Open Government Licence), no account needed. Confirm when
                         # historic_england.py is built in Sprint 1.
```

**Cost estimate over 30 days:**
- Gemini 2.5 Flash: ~$5–15 total (primary LLM, minimal calls)
- Groq: free tier sufficient for model eval experiment
- All other APIs: free tiers sufficient for dissertation volumes
- Total expected spend: under $20

---

## Evidence Manifest Schema

Every search produces an evidence manifest alongside the CON29 JSON.
This is the audit trail. It is as important as the CON29 output itself.

```json
{
  "search_id": "7f82a91b",
  "property_address": "14 Amhurst Road, Hackney, London E8 1LL",
  "uprn": "100021234567",
  "borough": "hackney",
  "search_timestamp": "2026-07-22T14:23:11Z",
  "sources": [
    {
      "con29_question": "1.1a",
      "question_text": "Has a planning permission been granted or refused?",
      "answer": true,
      "answer_detail": "3 planning applications found",
      "confidence": "HIGH",
      "source_type": "Official REST API",
      "source_name": "planning.data.gov.uk",
      "source_url": "https://www.planning.data.gov.uk/entity.json?...",
      "retrieved_timestamp": "2026-07-22T14:23:14Z",
      "document_reference": "2024/0123/FUL",
      "cited_text": "Permission is hereby granted for...",
      "coverage_flag": "auto"
    },
    {
      "con29_question": "3.3a",
      "question_text": "Is the property the subject of any drainage notice?",
      "answer": null,
      "confidence": null,
      "source_type": null,
      "coverage_flag": "manual",
      "manual_action_required": "Submit EIR Reg 5(1) request to Thames Water / Hackney drainage authority",
      "eir_template_generated": true
    }
  ],
  "coverage_summary": {
    "auto": 12,
    "agent_navigated": 4,
    "manual": 8,
    "total_questions": 24
  }
}
```

---

## CON29 Output Schema

```python
from pydantic import BaseModel, model_validator
from typing import Literal

class CON29Field(BaseModel):
    model_config = {"strict": True}

    question_id: str
    question_text: str
    answer: bool | str | None
    answer_detail: str | None
    confidence: Literal["HIGH", "MEDIUM", "LOW"] | None
    source_name: str | None
    source_url: str | None
    cited_text: str | None
    coverage_flag: Literal["auto", "agent_navigated", "manual", "unavailable"]
    retrieval_method: Literal["api", "gis", "dataset", "html", "pdf_llm", "playwright", "none"]
    conflict_detected: bool = False
    conflict_note: str | None = None

    @model_validator(mode="after")
    def cited_text_required_for_pdf_llm(self):
        if self.retrieval_method == "pdf_llm" and self.cited_text is None:
            raise ValueError(
                "cited_text must be provided for all pdf_llm extractions"
            )
        return self


class PropertySearchResult(BaseModel):
    search_id: str
    property_address: str
    uprn: str | None
    borough: Literal["bristol", "hackney"]
    search_timestamp: str
    fields: list[CON29Field]
    coverage_summary: dict[str, int]
    overall_confidence: Literal["HIGH", "MEDIUM", "LOW", "INDETERMINATE"]
    conflicts_detected: int
    eir_requests_generated: int
    system_notes: list[str]
```

---

## Repository Structure

```
con29-search/
├── PROJECT_ROADMAP.md          ← this file — always update it
├── .env                        ← never commit
├── .env.template               ← commit this
├── .gitignore
├── requirements.txt
├── README.md
│
├── src/
│   ├── __init__.py
│   ├── models.py               ← Pydantic schemas (CON29Field, PropertySearchResult)
│   ├── con29_registry.py       ← All CON29R questions, IDs, descriptions, bucket classification
│   │
│   ├── resolver/
│   │   ├── __init__.py
│   │   └── property_resolver.py  ← address → UPRN → coordinates → polygon
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py       ← dispatches agents, manages retrieval order
│   │   ├── planning_agent.py     ← planning.data.gov.uk, council registers
│   │   ├── gis_agent.py          ← ArcGIS REST, WFS, Historic England, TPO layers
│   │   └── document_agent.py     ← PDF download, PyMuPDF extraction, LLM call
│   │
│   ├── adapters/               ← one file per data source
│   │   ├── __init__.py
│   │   ├── planning_data_gov.py  ← planning.data.gov.uk REST adapter
│   │   ├── hmlr_llc1.py          ← HMLR LLC1 REST adapter
│   │   ├── historic_england.py   ← Historic England listed buildings adapter
│   │   ├── bristol_gis.py        ← Bristol Council GIS adapter
│   │   └── hackney_portal.py     ← Hackney planning register adapter
│   │
│   ├── normalisation/
│   │   ├── __init__.py
│   │   ├── normaliser.py         ← maps council terms to canonical CON29 schema
│   │   └── terminology_map.py    ← lookup tables for council-specific terminology
│   │
│   ├── extraction/
│   │   ├── __init__.py
│   │   ├── pdf_extractor.py      ← PyMuPDF text extraction + section finder
│   │   └── llm_extractor.py      ← Gemini call for unstructured text only
│   │
│   ├── mapping/
│   │   ├── __init__.py
│   │   └── con29_mapper.py       ← canonical fields → CON29 question answers
│   │
│   ├── validation/
│   │   ├── __init__.py
│   │   └── validator.py          ← cross-source conflict detection
│   │
│   ├── confidence/
│   │   ├── __init__.py
│   │   └── scorer.py             ← assigns confidence per field based on source tier
│   │
│   ├── eir/
│   │   ├── __init__.py
│   │   └── request_generator.py  ← generates EIR Reg 5(1) letter templates for Bucket 3
│   │
│   ├── report/
│   │   ├── __init__.py
│   │   ├── evidence_manifest.py  ← builds and serialises the evidence manifest JSON
│   │   └── pdf_report.py         ← generates human-readable PDF CON29 report
│   │
│   └── storage/
│       ├── __init__.py
│       └── session_store.py      ← ephemeral per-search folder, cleanup on completion
│
├── ui/
│   └── app.py                  ← Gradio interface (Hugging Face Spaces entry point)
│
├── model_eval/
│   ├── documents/              ← 20 planning docs for model comparison experiment
│   ├── ground_truth.json       ← manually annotated field values
│   ├── run_eval.py             ← runs extraction across 3 models
│   └── results.csv             ← accuracy, latency, cost, JSON validity per model
│
├── tests/
│   ├── fixtures/
│   │   ├── bristol/            ← sample API responses for Bristol
│   │   └── hackney/            ← sample portal HTML/JSON for Hackney
│   ├── test_resolver.py
│   ├── test_planning_agent.py
│   ├── test_gis_agent.py
│   ├── test_document_agent.py
│   ├── test_normaliser.py
│   ├── test_llm_extractor.py
│   ├── test_mapper.py
│   └── test_pipeline.py
│
└── evaluation/
    ├── ground_truth/           ← law firm partner search results
    ├── runs/                   ← system output JSON per property per run
    ├── compare.py              ← system vs ground truth field-level comparison
    └── results.csv             ← aggregated evaluation metrics
```

---

## Test Property Set

> Lock this with the law firm partner BEFORE Sprint 2 begins.
> Do not change it once locked. Changing it after testing begins is evaluation contamination.

**Selection criteria:**
- 5 properties per borough (10 total)
- At least 2 per borough with known planning history (stress-tests planning agent)
- At least 1 per borough with a clean history (establishes baseline)
- At least 1 per borough in a conservation area (stress-tests GIS agent)
- Law firm partner has ground truth CON29 results for all 10

```
Borough A — Bristol:
  P1: [ADDRESS] — [UPRN] — [NOTES: e.g. clean history]
  P2: [ADDRESS] — [UPRN] — [NOTES: e.g. active planning app]
  P3: [ADDRESS] — [UPRN] — [NOTES: e.g. conservation area]
  P4: [ADDRESS] — [UPRN] — [NOTES: e.g. enforcement history]
  P5: [ADDRESS] — [UPRN] — [NOTES: e.g. listed building]

Borough B — Hackney:
  P1: [ADDRESS] — [UPRN] — [NOTES: e.g. clean history]
  P2: [ADDRESS] — [UPRN] — [NOTES: e.g. active planning app]
  P3: [ADDRESS] — [UPRN] — [NOTES: e.g. conservation area]
  P4: [ADDRESS] — [UPRN] — [NOTES: e.g. enforcement history]
  P5: [ADDRESS] — [UPRN] — [NOTES: e.g. listed building]
```

---

## 30-Day Sprint Plan

### Sprint 0 — Environment, Credentials & Property Resolution
**Days 1–4 | Foundation**

**Why this sprint exists:**
Every subsequent component depends on being able to resolve an address to a UPRN
and spatial polygon. If the property resolver is wrong, every downstream query
is wrong. This is also where credentials are established — missing API keys mid-project
causes lost days.

**What to build:**

**Development environment setup (do this before anything else):**

- [ ] Create a GitHub repository for the project
- [ ] Enable GitHub Codespaces on the repository (free tier: 60 hours/month)
- [ ] Open the Codespace in VS Code (browser or desktop — your choice)
- [ ] All development, testing, and API calls run inside the Codespace
- [ ] Store all API keys in Codespace Secrets via GitHub Settings → Codespaces → Secrets — these automatically become environment variables in every session
- [ ] Google Drive mounted via `google.colab.drive` is not needed — save outputs to the repository or download directly
- [ ] For the model eval experiment (Sprint 5 only): use Google Colab with the repo cloned in, API keys entered via `userdata.get()` in Colab's secret manager
- [ ] Hugging Face Spaces deployment (Sprint 6): push `ui/app.py` and `requirements.txt` to a separate HF Space repository; API keys go in HF Spaces Secrets
- [ ] Add a payment method to avoid session cutoff; expected cost $10–20 for the project

> **You never run anything locally. Everything runs in Codespaces or Colab.**

- [x] Create Python virtual environment (`python -m venv venv`, Python 3.11+) — n/a, project runs in Codespaces per the environment setup above
- [x] Install all dependencies from requirements.txt
- [x] Create `.env` from `.env.template`, populate all API keys — OS Places, OS Names, Google AI Studio, Groq all obtained; HMLR blocked (Business Gateway); Historic England likely not needed
- [ ] Register for and obtain:
  - [x] OS Names API key (already held — NOTE: not used by the resolver, see Architecture Decisions 2026-07-22; kept for potential gazetteer use)
  - [x] OS Places API key (osdatahub.os.uk — added to existing project; 60-day free trial, confirmed working with a real call 2026-07-25)
  - [ ] HMLR LLC1 — BLOCKED, see Current State / Troubleshooting Log
  - [ ] Historic England API key — likely not required at all, see Architecture Decisions 2026-07-22; to reconfirm when historic_england.py is built in Sprint 1
  - [x] Google AI Studio API key (obtained 2026-07-25 — not yet exercised by any code; first real call happens in Sprint 2's llm_extractor.py)
  - [x] Groq API key (obtained 2026-07-25 — not yet exercised by any code; first real call happens in Sprint 5's model comparison experiment)
- [x] Implement `src/resolver/property_resolver.py`:
  - Takes free-text address string
  - Calls **OS Places API** (not OS Names — see Architecture Decisions 2026-07-22) to resolve to UPRN + coordinates + match confidence
  - Calls planning.data.gov.uk `/entity` (point lookup, not polygon — see Architecture Decisions 2026-07-25) for local authority code
  - Returns: `uprn`, `lat`, `lon`, `local_authority_code`, `match_score`, `match_description` (`polygon_wkt` retained on the model but always `None` — see 2026-07-25 decision)
- [x] Implement `src/con29_registry.py` — REBUILT 2026-08-02 against a real St
  Albans CON29R/LLC1 exemplar (search ref A/2025/00248, Griff), replacing the
  roadmap's own paraphrases with verbatim official text. See Architecture
  Decisions & Changes, 2026-08-02, for the full account — including two
  significant corrections (tree preservation orders are real-form 3.9(m), not
  a standalone 3.7; Article 4 directions have no standalone CON29 Part 1
  question number at all) that are FLAGGED but NOT YET actioned in the
  already-built `gis_agent.py`/`planning_agent.py`, pending confirmation.
  - All CON29R questions with IDs, descriptions, bucket classification
  - Required fields: `question_id`, `question_text`, `bucket`, `primary_source`
- [x] Set up GitHub repository and push initial structure — confirmed pushed to `brainsnog/MAS`, GitHub Actions run green (2026-07-25)
- [~] Capture 3–5 fixture responses from each key API for test use — 2 real OS
  Places API fixtures captured (Bristol, Hackney) 2026-07-25; Bristol's real
  `?f=json` MapServer layer list and Hackney's real WFS `GetCapabilities` +
  TPO CSV added 2026-08-02 (see Sprint 2 §A). A DescribeFeatureType schema
  call was attempted 2026-08-02 but returned only a wrapper document with
  two unfollowed `xsd:import`s (see Architecture Decisions) — genuinely
  real, but doesn't close the geometry-field-name gap yet. Historic
  England's `/query` response body and any Gemini/Groq call remain
  outstanding; deferred by agreement with Griff to continue with the rest
  of Sprint 2 first

**How the property resolver works (corrected 2026-07-25 — see Architecture Decisions & Changes for both corrections below):**
```
Input: "122 Whiteladies Road, Bristol BS8 2RP"
         │
         ▼
OS Places API /find (dataset=DPA, output_srs=WGS84)
  → UPRN: 67678
    lat: 51.4686389, lon: -2.6140011
    match_score: 0.9, match_description: "GOOD"
    (NOT OS Names API — see Architecture Decisions, 2026-07-22:
    Names API cannot resolve a street address to a UPRN at all)
         │
         ▼
planning.data.gov.uk /entity.json?dataset=local-authority-district&latitude=..&longitude=..
→ local_authority_code: "bristol"
    (point lookup, NOT a polygon query — see Architecture Decisions, 2026-07-25:
    there is no `boundary` dataset on planning.data.gov.uk, and no free/open
    source of a property's own parcel polygon exists at all. Sprint 1's
    planning_agent.py queries every dataset — conservation-area, listed-building,
    TPO, etc. — the same way: by point, not by a pre-built property polygon)
```

Match confidence matters in practice, not just in theory: a real call for the
roadmap's own example address, "14 Amhurst Road, London E8 1LL", returned UPRN
10008231087, "41, AMHURST ROAD..." — number 14 doesn't exist on that street —
still labelled `MATCH_DESCRIPTION: "GOOD"` (score 0.8). `resolve()` surfaces
`match_score`/`match_description` precisely so callers can catch this rather
than silently trusting `results[0]`.

**Success criteria:**
- [x] `property_resolver.py` resolves a Bristol address to correct UPRN — confirmed 2026-07-25 with a real call ("122 Whiteladies Road, Bristol BS8 2RP" → UPRN 67678, MATCH 0.9 "GOOD"). Polygon dropped from this criterion — see Architecture Decisions, 2026-07-25 (no free/open source exists)
- [~] `property_resolver.py` resolves a Hackney address to correct UPRN — technically incomplete: the roadmap's own example address ("14 Amhurst Road") doesn't exist; a real call correctly returned the nearest genuine match (41 Amhurst Road, UPRN 10008231087) with match_score surfaced rather than silently substituted. Recommend re-confirming against one of the actual 5 locked Hackney test properties once the test property set exists (Sprint 2 gate) rather than treating this as fully closed on a fictional address
- [x] Resolver handles address not found gracefully (returns error, does not crash) — `PropertyNotFoundError`/`ResolverServiceError`, tested
- [~] CON29 registry contains all 28+ question groups with bucket classification —
  REASSESSED 2026-08-02 against a real CON29R exemplar rather than left as an
  estimate: 19 CONFIRMED top-level groups (question number printed explicitly
  in the real document) + 3 real questions found but held in a separate
  `UNCONFIRMED_NUMBERING` list pending a legible question number = 22 total,
  63 individual sub-question IDs, all real text. "28+" itself may have been
  an overestimate for CON29 Part 1 alone — reaching it might require CON29O
  (optional enquiries), a separate form this exemplar doesn't include; worth
  a direct conversation with Griff rather than silently padding the count to
  match a target that may itself need revising. See Architecture Decisions.
- [~] All API keys working — test call to each returns valid response — OS Places API confirmed working (2026-07-25). Google AI Studio and Groq keys obtained (2026-07-25) but not yet exercised by any code — no LLM call exists until Sprint 2 (Gemini) / Sprint 5 (Groq). HMLR blocked. Historic England likely not needed. Treating this criterion as satisfied for everything currently callable; the two LLM keys will get their first genuine test as a natural side effect of Sprint 2/5, not held open as a Sprint 0 blocker
- [x] `pytest tests/test_resolver.py` passes on fixture data — 6/6 passing, using REAL captured OS Places API responses (not illustrative data) as of 2026-07-25

---

### Sprint 1 — National Data Agents (Bucket 1, Part 1)
**Days 5–9 | High-confidence structured sources**

**Why this sprint exists:**
National datasets (Historic England, planning.data.gov.uk, HMLR) work the same
regardless of borough. Building these first gives you instant coverage of ~40% of
CON29 fields for both Bristol and Hackney simultaneously. These are the most reliable
components and will not break mid-project.

**What to build:**

**A. HMLR LLC1 Adapter** (`src/adapters/hmlr_llc1.py`)
- Queries HMLR LLC1 API by UPRN for Bristol (migrated)
- For Hackney (not migrated): marks all LLC1-sourced fields as `coverage_flag: "manual"`
- Returns: list of charges with type, description, instrument reference
- **BLOCKED as of 2026-07-22** — Business Gateway account required, not a self-serve key. See Current State / Troubleshooting Log. Build against a graceful-degradation stub (Bristol fields also `coverage_flag: "manual"` with a `blocked_reason`, not silently absent) until resolved — proposed 2026-07-25, pending confirmation

**B. Historic England Adapter** (`src/adapters/historic_england.py`)
- Queries HE listed buildings API by coordinates + radius (50m)
- Returns: `listed_building: bool`, `grade: str | None`, `list_entry: str | None`
- Maps to CON29 question 3.5
- No API key expected to be required — open ArcGIS REST/WFS data (see Architecture Decisions, 2026-07-22). Confirm this against a live call before assuming it

**C. Planning Data Agent** (`src/agents/planning_agent.py`)
- Queries planning.data.gov.uk **by point** (`latitude`/`longitude` from the property resolver), NOT by polygon — corrected 2026-07-25 (see Architecture Decisions & Changes): there is no `boundary` dataset and no free/open source of a property's own parcel polygon. Every dataset below is queried the same way `_lookup_local_authority` already does it in `property_resolver.py`:
  - `dataset=planning-application` → CON29 1.1a–g
  - `dataset=conservation-area` → CON29 1.2, 3.11
  - `dataset=article-4-direction` → CON29 1.1h
  - `dataset=tree-preservation-order` → CON29 3.7
  - `dataset=listed-building` → CON29 3.5 (cross-check with HE)
  - `dataset=enforcement-notice` → CON29 1.1g
  - `dataset=brownfield-land` → CON29 3.13 (partial)
- Point-based queries return whichever entities have geometry covering that point — no polygon required
- Returns structured JSON per dataset

**D. Normalisation Layer** (`src/normalisation/normaliser.py`)
- Maps all returned data to canonical PropertyRecord
- Terminology map handles council-specific variations
- No LLM — pure lookup tables and rules

**Success criteria:**
- [~] HMLR adapter returns LLC1 charges for a Bristol test address — built as a graceful-degradation stub (returns `coverage_flag: "manual"` + `blocked_reason`, not charges) per the confirmed Business Gateway blocker; will return real charges once HMLR_BG_USERNAME/PASSWORD exist. Tested (5/5) against the stub's own contract, not against real charges, since no real Bristol call is possible yet. **Accepted as complete for Sprint 1's purposes** — the blocker is external (HMLR account access), not a build gap, and the stub's contract is exactly what Sprint 3's mapper needs regardless of when the real API call lands
- [x] Historic England adapter correctly identifies a known listed building — built and tested (7/7). Layer-discovery verified against a real `?f=json` call 2026-07-25 and fixed to explicitly prefer the points layer over the polygon layer (both exist on this service) rather than relying on array order — see Architecture Decisions. Residual, explicitly lower-risk item not blocking closure: exact attribute-key casing on a real `/query` call is still unconfirmed, absorbed defensively by case-insensitive substring matching
- [x] Planning agent returns planning applications for both a Bristol and Hackney address — tested against mocked responses covering both; real-call confirmation still pending (lower risk, query shape already confirmed correct from the resolver's local-authority lookup)
- [x] Planning agent returns conservation area status for both boroughs — same caveat as above
- [x] Normaliser maps varied terminology to canonical fields without error — 13/13 tests pass, including a deliberate Article-4-vs-TPO semantic distinction (None-means-unconfirmed vs False-means-confirmed-absent) and a real cross-source conflict check between Historic England and planning.data.gov.uk for listed buildings
- [x] All adapters return empty result gracefully (not crash) when no data found — confirmed for HMLR (always), Historic England (no-match case tested), Planning Data Agent (per-dataset failure doesn't abort others, tested)
- [x] `pytest tests/test_planning_agent.py` and `test_gis_agent.py` pass on fixtures — 37/37 passing across the whole Sprint 0 + Sprint 1 suite (note: `test_gis_agent.py` doesn't exist as a separate file yet — GIS/TPO/rights-of-way spatial layers are Sprint 2's job per the roadmap's own repository structure; the equivalent Sprint 1 coverage lives in `test_planning_agent.py`'s tree-preservation-order dataset query)
- [x] Sprint 1 covers at least 10 CON29 question groups for Bristol — **CONFIRMED programmatically 2026-07-25** via `scripts/tally_sprint1_coverage.py` (run: `python3 -m scripts.tally_sprint1_coverage`, locked in by `tests/test_tally_sprint1_coverage.py`): 10 groups architecturally covered (meets the criterion exactly), of which 8 deliver real Bristol data today — 1.1a-f, 1.1g, 1.1h-i, 1.2, 3.11, 3.13, 3.5, 3.7 — and 2 (3.1, 3.12) are correctly excluded from "functional today" because they're HMLR-stub-blocked, not because anything is unbuilt

**Sprint 1 closing checklist — all three items resolved 2026-07-25:**
- [x] **1. Historic England layer-discovery verification** — RESOLVED. Real call confirmed both a points and polygon layer exist; fixed to explicitly prefer points, with regression tests proving it doesn't depend on array order
- [x] **2. Push to GitHub and confirm CI green** — CONFIRMED by Griff, green check seen
- [x] **3. Tally CON29 question-group coverage for Bristol** — CONFIRMED, 10 architectural / 8 functional (see success criteria row above)

**SPRINT 1 IS FORMALLY CLOSED.** Next: Sprint 2 — GIS Agent & Document Agent (Days 10-15), not yet started.

---

### Sprint 2 — GIS Agent & Document Agent
**Days 10–15 | Spatial queries and PDF extraction**

**Why this sprint exists:**
GIS layers give you TPOs, rights of way, and spatial constraints that APIs do not
expose as clean JSON. The document agent handles PDFs — the place where LLM use
is genuinely justified. Together these two agents cover the remaining Bucket 1 fields
and introduce the LLM extraction component.

**What to build:**

**A. GIS Agent** (`src/agents/gis_agent.py`) — BUILT 2026-08-02, see Architecture
Decisions & Changes for the full correction. Original spec below is stale
(struck through in spirit, kept for history — do not rebuild against it):

~~Queries ArcGIS REST endpoints for both boroughs. Performs spatial
intersection: does the property polygon intersect this layer? Queries: TPO
layer, rights of way layer, flood zone layer, contamination register.~~

**What was actually built, and why it differs:**
- Bristol and Hackney do **not** share a backend. Bristol runs a legacy
  ArcGIS Server (`maps2.bristol.gov.uk/.../ext/INSPIRE/MapServer`, real
  19-layer list confirmed via `?f=json`). Hackney runs **GeoServer (WFS
  2.0)**, not ArcGIS at all — confirmed by inspecting the config Hackney's
  own public tree map loads client-side, not assumed by analogy. Two backend
  query functions (`_query_arcgis`, `_query_wfs`) behind one per-borough
  dispatcher, same shape as `hmlr_llc1.py`'s per-borough branching.
- No "property polygon intersects this layer" query exists, for the same
  reason planning_agent.py was corrected on 2026-07-25: there is no free
  source of a property's own parcel polygon. Queries by point instead, with
  a confirmed 15m buffer specifically for TPO (see Architecture Decisions) —
  an exact intersects test for polygon designation layers (Article 4,
  conservation area).
- **Flood zone dropped from scope** — it is not a CON29R question anywhere
  in `con29_registry.py`; flood risk is a separate search product. Not
  silently omitted — logged as a real scope correction in Architecture
  Decisions, not an oversight.
- Rights of way (both boroughs) and Bristol's contaminated-land source
  remain genuinely unconfirmed/unavailable as of 2026-08-02 — see
  `gis_agent.py`'s own module docstring "KNOWN GAPS" for the detail on each,
  and Architecture Decisions for why these are treated as findings, not bugs.

**B. Document Agent** (`src/agents/document_agent.py`)
Sub-components:

  1. `pdf_extractor.py` — PyMuPDF:
     - Downloads PDF from URL
     - Extracts full text
     - Identifies relevant sections by keyword proximity
       (e.g. finds paragraphs containing "decision", "approved", "refused")
     - Returns: relevant text sections only (not full document)

  2. `llm_extractor.py` — Gemini 2.5 Flash:
     - Input: relevant text sections from pdf_extractor (never full PDF)
     - Prompt: extract specific fields, return JSON, cite exact text
     - Output: `{field_name: value, cited_text: "exact quote"}`
     - Pydantic validates output — if `cited_text` is null, retry once
     - Max 2 LLM calls per document

  3. Session storage (`src/storage/session_store.py`):
     - Creates `/tmp/searches/{search_id}/` on search start
     - Raw PDFs → `/tmp/searches/{search_id}/raw/`
     - Extracted JSON → `/tmp/searches/{search_id}/extracted/`
     - Deletes entire folder after report generation

**C. Lock test property set:**
- Law firm partner must confirm 10 test properties before Sprint 3
- Populate the Test Property Set table in this document

**Success criteria:**
- [~] GIS agent correctly identifies a property within a Bristol conservation area
      — CANNOT BE MET AS WRITTEN, flagged rather than silently reinterpreted:
      Bristol's confirmed INSPIRE MapServer layers (19 total, see Architecture
      Decisions) do NOT include a conservation area layer. Bristol conservation
      area is already opportunistically covered by `planning_agent.py` (Sprint 1)
      via planning.data.gov.uk's national dataset, not by gis_agent.py — same
      overlap pattern already documented in planning_agent.py's own module
      docstring for Article 4. No further action needed unless that national
      dataset turns out to have gaps for Bristol specifically.
- [x] GIS agent correctly identifies a TPO on a known Hackney property — built
      and tested (12/12 new tests, network-mocked). Real layer name confirmed
      (`planning:tpo_point_as_area`) but not yet run against a real known-TPO
      Hackney address; that live confirmation is still outstanding.
- [ ] PDF extractor downloads and extracts text from a planning decision notice
- [ ] LLM extractor returns valid Pydantic-validated JSON from extracted text
- [ ] LLM extractor provides `cited_text` for every extracted field
- [ ] Session store creates and cleans up folder correctly
- [ ] `pytest tests/test_document_agent.py` passes on fixture PDFs
- [ ] Test property set locked and table above populated

---

### Sprint 3 — CON29 Mapper, Confidence Engine & Validation
**Days 16–20 | Turning retrieved data into CON29 answers**

**Why this sprint exists:**
This is the translation layer between raw retrieved data and the CON29 form.
It is mostly deterministic logic — no LLM. Getting this right means the system
produces legally-structured output rather than a bag of data.

**What to build:**

**A. CON29 Mapper** (`src/mapping/con29_mapper.py`)
- Takes normalised PropertyRecord as input
- Applies mapping rules: which canonical field(s) answer which CON29 question
- Returns: list of CON29Field objects (Pydantic models)
- Handles one-to-many: one canonical field may answer multiple CON29 questions
- Handles many-to-one: multiple fields may combine to answer one CON29 question
- Assigns `coverage_flag` per field: `auto`, `agent_navigated`, `manual`, `unavailable`

Example mapping rule:
```python
# CON29 1.1a: Has a planning permission been granted or refused?
def map_planning_history(record: PropertyRecord) -> CON29Field:
    apps = record.planning_applications
    if apps is None:
        return CON29Field(
            question_id="1.1a",
            answer=None,
            coverage_flag="unavailable",
            retrieval_method="none"
        )
    return CON29Field(
        question_id="1.1a",
        answer=len(apps) > 0,
        answer_detail=f"{len(apps)} planning application(s) found",
        coverage_flag="auto",
        retrieval_method="api",
        confidence="HIGH",
        source_name="planning.data.gov.uk",
        ...
    )
```

**B. Confidence Scorer** (`src/confidence/scorer.py`)
- Assigns `confidence` (HIGH/MEDIUM/LOW) to each CON29Field based on source tier
- Computes `overall_confidence` for PropertySearchResult:
  - HIGH: all auto fields are HIGH confidence, no conflicts
  - MEDIUM: mix of HIGH and MEDIUM, or minor conflicts resolved
  - LOW: any LOW confidence fields in critical areas, or unresolved conflicts
  - INDETERMINATE: too many MANUAL fields to assess overall reliability

**C. Validation Agent** (`src/validation/validator.py`)
- Iterates all CON29Fields
- For each field, checks if multiple sources provided an answer
- If answers conflict (e.g. API says False, GIS says True):
  - Sets `conflict_detected: True`
  - Sets `conflict_note` explaining the discrepancy
  - Optionally calls LLM to interpret conflict (single call, brief prompt)
- Returns updated list of CON29Fields with conflicts flagged

**D. EIR Request Generator** (`src/eir/request_generator.py`)
- For every field with `coverage_flag: "manual"`:
  - Identifies the correct authority to request from (borough council, county highways, water authority)
  - Generates pre-populated EIR Reg 5(1) letter template in plain text
  - Letter specifies: property address, UPRN, exact data requested, legal basis
- Returns list of EIR request templates
- These are shown in the UI and included in the report — NOT auto-sent

**Success criteria:**
- [ ] Mapper produces valid Pydantic CON29Field for every question in the registry
- [ ] Mapper correctly assigns `coverage_flag: "manual"` for all Bucket 3 fields
- [ ] Confidence scorer assigns HIGH to API-sourced fields, MEDIUM to PDF-extracted fields
- [ ] Validator correctly detects a seeded conflict between two sources
- [ ] EIR generator produces a coherent, legally-cited letter template for a Bucket 3 field
- [ ] `pytest tests/test_mapper.py` passes
- [ ] Running the partial pipeline (resolver → agents → mapper) on 2 Bristol properties produces valid CON29Field output

---

### Sprint 4 — Evidence Manifest, Report & Pipeline Integration
**Days 21–24 | End-to-end pipeline and outputs**

**Why this sprint exists:**
All components now exist. This sprint wires them together into a single callable
pipeline and produces the two primary outputs: the evidence manifest JSON and the
PDF report. By end of this sprint, the system is functionally complete.

**What to build:**

**A. Evidence Manifest Builder** (`src/report/evidence_manifest.py`)
- Iterates all CON29Fields from the mapper output
- For each field, assembles the manifest entry (see schema above)
- Writes to `/tmp/searches/{search_id}/evidence/manifest.json`
- This is the audit trail — the most important single output

**B. PDF Report Generator** (`src/report/pdf_report.py`)
- Reads CON29Fields and evidence manifest
- Generates a structured PDF with:
  - Cover page: property address, search date, overall confidence
  - Section per CON29 category (Planning, Highways, Drainage, Other)
  - Per-field: question, answer, confidence badge, source name
  - Conflicts highlighted in amber
  - Manual fields listed with EIR request templates
  - Evidence appendix: all source URLs and timestamps
- Library: ReportLab or WeasyPrint (choose based on template flexibility)

**C. Main Pipeline Orchestrator** (`src/agents/orchestrator.py`)
```python
async def run_search(address: str) -> PropertySearchResult:
    # 1. Resolve property
    property_info = await property_resolver.resolve(address)

    # 2. Dispatch retrieval agents in parallel
    planning_data, gis_data, documents = await asyncio.gather(
        planning_agent.retrieve(property_info),
        gis_agent.retrieve(property_info),
        document_agent.retrieve(property_info),
    )

    # 3. Normalise
    record = normaliser.normalise(planning_data, gis_data, documents)

    # 4. LLM extraction (only for documents)
    if documents.pdfs:
        record = await llm_extractor.extract(record, documents)

    # 5. Map to CON29
    fields = con29_mapper.map(record)

    # 6. Score confidence
    fields = confidence_scorer.score(fields)

    # 7. Validate / detect conflicts
    fields = validator.validate(fields)

    # 8. Generate EIR requests for manual fields
    eir_requests = eir_generator.generate(fields)

    # 9. Build evidence manifest
    manifest = evidence_manifest.build(property_info, fields, eir_requests)

    # 10. Generate PDF report
    pdf_path = pdf_report.generate(property_info, fields, manifest)

    # 11. Clean up raw files
    session_store.cleanup(property_info.search_id)

    return PropertySearchResult(...)
```

**D. CLI entry point** (`scripts/run_search.py`)
```
python scripts/run_search.py --address "14 Amhurst Road, Hackney, London E8 1LL"
```

**Success criteria:**
- [ ] `run_search.py` completes end-to-end for at least 1 Bristol address
- [ ] `run_search.py` completes end-to-end for at least 1 Hackney address
- [ ] Evidence manifest is produced for both runs with correct source entries
- [ ] PDF report is produced and human-readable
- [ ] EIR templates generated for at least 1 Bucket 3 field per borough
- [ ] Session cleanup deletes raw PDFs after report generation
- [ ] Wall-clock time logged for both runs
- [ ] `pytest tests/test_pipeline.py` passes end-to-end on fixture data

---

### Sprint 5 — Model Comparison Experiment & Evaluation
**Days 25–27 | Dissertation methodology**

**Why this sprint exists:**
The model comparison experiment turns the LLM selection decision into research.
The evaluation against law firm ground truth produces the dissertation's primary
quantitative findings. Both must be complete before the dissertation can be written.

**What to build:**

**A. Model Comparison Experiment** (`model_eval/run_eval.py`)

Collect 20 planning documents (mix of Bristol and Hackney):
- 8 planning decision notices
- 5 enforcement notices
- 4 committee reports
- 3 officer reports

Manually annotate ground truth fields for all 20 (`model_eval/ground_truth.json`).

For each of 3 models (Gemini 2.5 Flash, Qwen 3 8B via Groq, Llama 3.1 8B via Groq):
- Run same extraction prompt on same 20 documents
- Record: accuracy per field, JSON validity (Pydantic pass/fail), latency, cost
- Save to `model_eval/results.csv`

Report format for dissertation:

| Model | Accuracy | JSON Validity | Latency (avg) | Cost per doc |
|---|---|---|---|---|
| Gemini 2.5 Flash | TBD | TBD | TBD | TBD |
| Qwen 3 8B (Groq) | TBD | TBD | TBD | TBD |
| Llama 3.1 8B (Groq) | TBD | TBD | TBD | TBD |

**B. Ground Truth Evaluation** (`evaluation/compare.py`)

Run the full pipeline on all 10 test properties.
Compare output against law firm partner ground truth field by field.

Metrics:
- **Auto-retrieval coverage rate:** % of fields the system auto-retrieved (vs total)
- **Field accuracy:** % of auto-retrieved answers matching ground truth
- **False positive rate:** system says infringement exists, ground truth says no
- **False negative rate:** system misses an infringement the ground truth found
- **Conflict detection rate:** % of genuine conflicts the validator flagged
- **Wall-clock time:** system time vs estimated manual search time
- **Borough comparison:** all metrics split by Bristol vs Hackney

Save results to `evaluation/results.csv`.

**Success criteria:**
- [ ] Model eval run complete across all 3 models on all 20 documents
- [ ] Results CSV populated with accuracy, validity, latency, cost per model
- [ ] Full pipeline run on all 10 test properties, outputs saved
- [ ] Ground truth comparison script produces field-level metrics
- [ ] Bristol vs Hackney coverage gap quantified (this is the headline finding)
- [ ] Wall-clock time comparison documented
- [ ] Zero cases where `cited_text` is null on a pdf_llm extraction in final output

---

### Sprint 6 — Gradio UI & Hugging Face Spaces Deployment
**Days 28–29 | Demo interface**

**Why this sprint exists:**
An examiner clicking a link and seeing results is categorically more impressive
than a CLI script. The UI is not a nice-to-have — it is the demonstration vehicle
for the proof of concept. Two days is sufficient for a functional Gradio interface.

**What to build:**

```python
# ui/app.py — Gradio interface

import gradio as gr
from src.agents.orchestrator import run_search
import asyncio

def search(address: str, borough: str):
    result = asyncio.run(run_search(address))
    # Format for display
    return (
        format_summary(result),      # Text summary tab
        format_fields_table(result), # CON29 fields tab
        result.evidence_manifest,    # Evidence JSON tab
        generate_pdf_path(result),   # Download button
    )

with gr.Blocks(title="CON29 Automated Search") as demo:
    gr.Markdown("## CON29 Automated Property Search")
    gr.Markdown("Enter a property address to retrieve CON29-relevant data automatically.")

    with gr.Row():
        address_input = gr.Textbox(label="Property Address", placeholder="14 Amhurst Road, Hackney, London E8 1LL")
        borough_select = gr.Dropdown(["Bristol", "Hackney"], label="Borough")
        search_btn = gr.Button("Run Search", variant="primary")

    with gr.Tabs():
        with gr.Tab("Summary"):
            summary_output = gr.Markdown()
        with gr.Tab("CON29 Fields"):
            fields_table = gr.Dataframe()
        with gr.Tab("Evidence"):
            evidence_output = gr.JSON()
        with gr.Tab("Download"):
            pdf_download = gr.File(label="Download PDF Report")

    search_btn.click(
        fn=search,
        inputs=[address_input, borough_select],
        outputs=[summary_output, fields_table, evidence_output, pdf_download]
    )

demo.launch()
```

**Hugging Face Spaces deployment:**
- Create HF Space (Gradio SDK, Python 3.11)
- Add `requirements.txt` to Space repo
- Add secrets (API keys) via HF Spaces Secrets UI — never hardcode
- Test all 10 evaluation properties via the live UI

**Success criteria:**
- [ ] Gradio app runs locally without error
- [ ] Gradio app deployed to Hugging Face Spaces and accessible via public URL
- [ ] All 4 tabs functional (summary, fields, evidence, download)
- [ ] PDF report downloads correctly from the UI
- [ ] All 10 test properties return valid output via the live UI
- [ ] API keys stored as HF Secrets, not in code

---

### Sprint 7 — Hardening, Documentation & Dissertation Support
**Day 30 | Final polish**

**What to do:**
- [ ] Add exponential backoff retry to all external HTTP calls
- [ ] Add graceful degradation: any agent failure → field marked `unavailable`, pipeline continues
- [ ] Add structured logging: every agent call logs source, latency, status, field covered
- [ ] Write `README.md` with setup instructions, API key requirements, run commands
- [ ] Clean all `# TODO` comments
- [ ] Run full 10-property evaluation one final time, record final metrics
- [ ] Tag release: `git tag v1.0.0-poc && git push --tags`
- [ ] Archive one complete run per borough with logs for dissertation appendix
- [ ] Confirm live HF Spaces URL is stable for submission

**Success criteria:**
- [ ] System runs 5 consecutive times on fixture data without error
- [ ] System runs on 2 live addresses per borough without error
- [ ] README sufficient for a new developer to set up from scratch
- [ ] Final evaluation metrics recorded and match Sprint 5 results
- [ ] `v1.0.0-poc` tagged and pushed
- [ ] HF Spaces URL confirmed working

---

## Architecture Decisions & Changes

> Every significant decision must be recorded here. Future Claude instances:
> if you want to change something, explain why here first.

| Date | Decision | Reason |
|---|---|---|
| 2026-07-22 | Replaced LangGraph with plain Python asyncio orchestrator | LangGraph adds complexity without benefit at this pipeline scale; plain async is more readable and debuggable for a solo developer |
| 2026-07-22 | Playwright demoted to last resort (not primary retrieval) | Playwright is brittle and maintenance-heavy; structured sources cover ~80% of CON29 fields reliably |
| 2026-07-22 | Replaced Mole Valley with Hackney as Borough B | Lawyer partner direct experience; Hackney cyberattack creates documented real-world legacy failure case |
| 2026-07-22 | LLM use restricted to PDF extraction, terminology normalisation, conflict detection | 80% of CON29 pipeline is data engineering; LLM where deterministic fails, not by default |
| 2026-07-22 | Added model comparison experiment (Gemini vs Qwen vs Llama) | Turns model selection into methodology contribution; provides empirical justification for LLM choice |
| 2026-07-22 | Added Gradio UI on HF Spaces as demo deliverable | Examiner-facing demo is more persuasive than CLI; HF Spaces is free and reliable for dissertation volumes |
| 2026-07-22 | EIR requests generated as templates, not auto-dispatched | Keeps system within safe scope; human oversight for regulatory requests; appropriate for PoC stage |
| 2026-07-22 | Development runs entirely in GitHub Codespaces (main dev) and Google Colab (Sprint 5 model eval only) — no local execution | Keeps API keys centralised in Codespaces/Colab/HF Secrets rather than scattered across a local `.env`; removes local environment drift; consistent with cloud-hosted demo (HF Spaces) |
| 2026-07-22 | HMLR credential model changed from `HMLR_API_KEY` to `HMLR_BG_USERNAME`/`HMLR_BG_PASSWORD` (Basic Auth) | There is no self-serve HMLR API key. LLC1 access is via Business Gateway, which requires an active Business e-services account. Logged as a blocker, not resolved yet |
| 2026-07-22 | Removed `HISTORIC_ENGLAND_KEY` as a required credential (kept commented, to confirm in Sprint 1) | Historic England's NHLE listed buildings / conservation area data is published as open data (ArcGIS REST / WFS) under the Open Government Licence — no account or key found to be necessary |
| 2026-07-22 | Property resolver rebuilt against **OS Places API** (`OS_PLACES_API_KEY`, DPA dataset) instead of OS Names API for the address → UPRN step | OS Names API is a gazetteer of named places (towns, roads) and explicitly does not resolve or return a UPRN for a specific street address. OS Places API (AddressBase-based) is OS's own recommended product for address/UPRN/geocoding lookups. OS Names API key is retained for potential gazetteer use but is not part of the resolver's critical path |
| 2026-07-25 | Removed the property-boundary-polygon lookup (`_lookup_boundary_polygon`, `dataset=boundary`) from `property_resolver.py`. `polygon_wkt` on `ResolvedProperty` is retained as a field but is now always `None`. Sprint 1's `planning_agent.py` (not yet built) must query planning.data.gov.uk by point (`latitude`/`longitude` intersection) rather than by a pre-built property polygon | Verified against live docs at https://www.planning.data.gov.uk/docs: there is no `boundary` dataset on planning.data.gov.uk, and no free/open source of a property's own parcel polygon exists at all — that's HMLR's licensed INSPIRE Index Polygons product, not something OS Places or planning.data.gov.uk provide. The API's actual, documented spatial-query shape is the reverse of what was assumed: pass a point (lat/lon) and a list of datasets, and it returns whichever entities (conservation-area, listed-building, TPO, etc.) have geometry covering that point — `entity.json?latitude=..&longitude=..&dataset=conservation-area&dataset=listed-building&...`. This is simpler than the original design and doesn't require a polygon the free stack can't source. Confirmed at the same time: `dataset=local-authority-district` with `latitude`/`longitude` (used by `_lookup_local_authority`) is a real, documented query and needed no change |
| 2026-07-25 | Added `.github/workflows/tests.yml` — pytest now runs automatically on every push via GitHub Actions, in addition to (not instead of) Codespaces. Refines, does not override, Sprint 0's "you never run anything locally — everything runs in Codespaces or Colab" instruction | User is on a 60-hour free trial of Codespaces and wants to reserve those hours for the actual LLM-latency-sensitive build work. `tests/test_resolver.py` uses `httpx.MockTransport` — no real network calls, no LLM calls — so it doesn't need Codespaces at all, and OS Places fixture capture is a single HTTP GET reachable from any browser or terminal. GitHub Actions' free tier is separate from and does not draw down Codespaces hours. This does not change where the actual LLM-dependent build work happens (still Codespaces/Colab per the original rule) — only where the free, network-mocked test suite runs |
| 2026-07-25 | Added `output_srs=WGS84` to the OS Places API request in `_call_os_places_find` | Genuine bug, not a design choice: OS Places API defaults to EPSG:27700 (BNG) and omits LAT/LNG entirely unless WGS84 output is explicitly requested. As written before this fix, `resolve()` would raise `ResolverServiceError` on every real address, since `dpa.get("LAT")`/`dpa.get("LNG")` would always be `None`. Confirmed against a real API response 2026-07-25 — see Troubleshooting Log |
| 2026-07-25 | Added `match_score: float` and `match_description: str` to `ResolvedProperty`, sourced from OS Places API's own `MATCH`/`MATCH_DESCRIPTION` fields | A real call for the roadmap's own example address ("14 Amhurst Road, London E8 1LL") returned a different house number (41, not 14 — 14 doesn't exist) labelled `MATCH_DESCRIPTION: "GOOD"` (score 0.8). Every other layer of this system (`CON29Field.confidence`, `overall_confidence`) exists specifically so nothing gets trusted silently; the resolver, at the very front of the pipeline, needs the same property. `resolve()` surfaces the signal but deliberately does not itself decide what counts as "close enough" — that's for the caller (CLI, orchestrator, eventual UI) to judge |
| 2026-07-25 | Built `src/adapters/hmlr_llc1.py` as a graceful-degradation stub | Business Gateway blocked (see Troubleshooting Log, 2026-07-22) — rather than leave a hole where this adapter should be, it returns `coverage_flag: "manual"` for both boroughs with two deliberately distinct `blocked_reason` messages (Bristol: temporary/credentials; Hackney: structural/non-migration), never raises. `COVERS_QUESTIONS = ("3.1", "3.12")` cross-checked against `con29_registry.py`'s `primary_source` field — exact match. Noted for Sprint 3: `CON29Field`'s strict Pydantic schema has no dedicated field for `blocked_reason` — the mapper will need to fold it into `answer_detail` |
| 2026-07-25 | Built `src/adapters/historic_england.py` with runtime layer discovery (`?f=json`, match "listed building" in the layer name) rather than a hardcoded layer index | Confirmed real, keyless, OGL-licensed FeatureServer exists, but every concrete layer-index example found while researching belonged to a different council's own mirror with independent numbering, not this national service — hardcoding a guess risked silently querying the wrong layer. Attribute keys matched case-insensitively by substring for the same reason (exact casing unconfirmed without a live call) |
| 2026-07-25 | Built `src/agents/planning_agent.py` querying planning.data.gov.uk BY POINT across all 7 datasets in Sprint 1 §C, in parallel via `asyncio.gather`, with per-dataset graceful degradation | Point-based, not polygon-based, per the resolver's 2026-07-25 decision above. A single dataset failing must not abort the others — same principle as the resolver's local-authority lookup. Deliberately queries 1.1h (Article 4) even though its registry `primary_source` is the council website (Bucket 2): this is opportunistic best-tier-first checking, not a claim of authority — an empty result means "not found here", not "confirmed absent". The roadmap's own Sprint 1 §C table lists 1.1g under two different datasets; kept as written rather than silently resolved |
| 2026-07-25 | Built `src/normalisation/terminology_map.py` + `src/normalisation/normaliser.py`, defining `PropertyRecord` as an intermediate canonical model (not Sprint 3's `CON29Field`/`PropertySearchResult`) | Gives Sprint 1's three adapters/agents one common shape to land in ahead of Sprint 3. `article_4_direction` is `Optional[bool]` (`None` = not found in this source, not confirmed absent) while `tree_preservation_order` is a plain `bool` — deliberately different, reflecting the Bucket 2 vs Bucket 1 distinction already established for these two fields. Implemented Sprint 1 §C's "cross-check with HE" instruction literally: `listed_building_source_conflict` is set and a warning logged whenever Historic England and planning.data.gov.uk's own listed-building dataset disagree, rather than trusting one silently |
| 2026-07-25 | Fixed `historic_england.py`'s layer discovery to explicitly prefer the points layer over the polygon layer, rather than relying on array order | Confirmed via a real `?f=json` call (Griff): this service has BOTH "Listed Building points" (id 0) and "Listed Building polygons" (id 3) — the earlier flagged risk was real, not hypothetical. The original code's choice of points was array-order luck; HE's own docs say the polygon layer only covers buildings listed/amended since April 2011, so relying on luck could have silently under-reported older listings. Two regression tests added, one with the array deliberately reordered, proving the fix doesn't depend on list order. This closes Sprint 1's closing-checklist item 1; items 2 (GitHub push/CI) and 3 (coverage tally) closed the same session — **Sprint 1 is formally closed as of 2026-07-25** |
| 2026-08-02 | Corrected Sprint 2's GIS Agent spec from "does the property polygon intersect this layer?" to point-based queries with a per-feature-type buffer, and split the backend into two: `_query_arcgis` (Bristol) and `_query_wfs` (Hackney) behind one per-borough dispatcher, same shape as `hmlr_llc1.py`'s branching | Same underlying reason as the resolver's 2026-07-25 correction — no free source of a property's own parcel polygon exists — but this sprint additionally discovered that **Bristol and Hackney don't even share a GIS backend**. Bristol runs a legacy ArcGIS Server (`maps2.bristol.gov.uk/.../ext/INSPIRE/MapServer`); Hackney runs GeoServer (WFS 2.0), not ArcGIS at all. This was confirmed, not assumed by analogy: Griff found it by inspecting the config Hackney's own public tree map loads client-side (a `vectorTileUrl` pointing at `map2.hackney.gov.uk/geoserver/gwc/...`), which led to the real WFS `GetCapabilities` endpoint. A single "GIS Agent queries ArcGIS" spec would have silently failed for one of the two boroughs |
| 2026-08-02 | Bristol's real layer IDs confirmed via a real `?f=json` call against the INSPIRE MapServer (19 layers total): `article_4_direction` = 1, TPO trunk (point) = 18, TPO canopy (polygon) = 17 (not used — see next row). Hackney's real typeNames confirmed via a real WFS `GetCapabilities` call (~700 layers): `planning:tpo_point_as_area`, `planning:article_4_direction`, `planning:conservation_area`, `planning:brownfield_register`, `pollution:part2a_site_investigated`, `pollution:part2a_site_potential_concern` | Same discipline as Historic England's layer discovery: a generic web search for "INSPIRE MapServer" surfaces an identically-named but differently-numbered service run by City of London — hardcoding a guessed layer ID risked silently querying the wrong council's data. Both real discovery documents are large (Hackney's especially, ~700 `FeatureType` entries) and are not committed verbatim to the repo; the confirmed layer IDs/names above are what's hardcoded in `gis_agent.py`, with the discovery session itself recorded here for provenance |
| 2026-08-02 | TPO query design: buffer approach confirmed with Griff, 15m radius (`TPO_BUFFER_M` in `gis_agent.py`), applied identically to both boroughs (Bristol's ArcGIS point layer via `distance`/`units` params, Hackney's WFS layer via a `DWITHIN` CQL filter) | Same shape as `historic_england.py`'s existing 50m radius pattern for listed buildings, reused deliberately rather than inventing a new query style. A tight "does the point fall exactly under this canopy/trunk feature" test is less forgiving of the property resolver's own address-matching imprecision (see `ResolvedProperty.match_score`, 2026-07-25) than what CON29 3.7 is actually asking |
| 2026-08-02 | Dropped "flood zone layer" from Sprint 2's GIS Agent scope | It is not a CON29R question anywhere in `con29_registry.py` — flood risk is a separate search product, not part of CON29. Confirmed with Griff before building rather than silently including or silently dropping it |
| 2026-08-02 | Sprint 2's original success criterion "GIS agent correctly identifies a property within a Bristol conservation area" cannot be met by `gis_agent.py` as built, and is not being force-fitted | Bristol's confirmed INSPIRE MapServer (19 layers, `?f=json`) has no conservation area layer. Bristol conservation area is already opportunistically covered by `planning_agent.py` (Sprint 1) via planning.data.gov.uk's national dataset — same overlap pattern already documented in that module's own docstring for Article 4. Flagged in the Sprint 2 checklist itself (marked `[~]`, not silently checked off or silently reinterpreted) rather than quietly redefining what the criterion means |
| 2026-08-02 | Built `src/agents/gis_agent.py` — TPO and Article 4 for both boroughs, plus conservation area, brownfield register, and Part 2A contaminated land for Hackney only. Rights of way (both boroughs) and Bristol's contaminated-land source are represented as `DatasetResult.unavailable_reason` (no network call attempted), same transparency principle as `hmlr_llc1.py`'s `blocked_reason` stubs, rather than silently omitted or silently invented | Hackney's `pollution:part2a_*` layers are a genuinely strong, legally precise find — Part 2A is the actual statutory contaminated-land regime under the Environmental Protection Act 1990, a direct match for CON29 3.13, not an approximation. Rights of way was searched for exhaustively on Hackney's side (all ~700 layers, nothing resembling a definitive map/footpath/bridleway found) and is being kept as a genuine digital-maturity finding for the dissertation rather than a gap to keep chasing indefinitely. 12/12 new tests pass (49/49 total across the whole suite), network-mocked, no live calls made yet |
| 2026-08-02 | Rebuilt `src/con29_registry.py` from scratch against a real St Albans CON29R/LLC1 exemplar (search ref A/2025/00248, Griff), replacing every paraphrased question_text with the real form's own verbatim wording. 63 sub-question entries across 19 confirmed top-level groups. Six previous group-level guesses removed as unevidenced by the real form: "1.1g Planning enforcement", "1.1h-i Article 4 directions", "3.2 Roadworks / traffic schemes", "3.3a-f Drainage and sewers", "3.4 Traffic management schemes", "3.8 Noise abatement zones" | The real form's own 1.1(a)-(l) turned out to be entirely about planning/listed-building consents and building-regulation certificates — no enforcement item, no Article 4 item anywhere within it. Real 3.6 is "Traffic Schemes" (12 real sub-items), real 3.7 is "Outstanding Notices" (7 real sub-items, matching what the previous registry had mislabeled as "3.6"), real 3.8 is "Contravention of building regulations" (nothing resembling "noise abatement zones" appears anywhere in the document under any number). Rather than silently drop the topics these guesses were gesturing at, three genuinely real questions found in the document without a legible printed number (SuDS/drainage matters, nearby road schemes, nearby railway schemes) are kept in a new `UNCONFIRMED_NUMBERING` list, deliberately not given a guessed numeric id — same "flag, don't invent" discipline as the HMLR and Hackney-geometry-field gaps. 8/8 new tests pass (57/57 total) |
| 2026-08-02 | FLAGGED, NOT YET ACTIONED: tree preservation orders are real-form question 3.9(m) (a sub-item of "Notices, orders, directions and proceedings under Planning Acts"), not a standalone "3.7" as `con29_registry.py` assumed until today AND as the already-built `gis_agent.py`/`planning_agent.py` still assume. Article 4 directions have no standalone CON29 Part 1 question number anywhere in the real document — plausibly LLC1-register-sourced (Part 1 LLC1 charges under the Local Land Charges Rules 1977) rather than a CON29 enquiry at all, though this specific exemplar property had no such charges to confirm either way. `con29_registry.py` has been corrected to match the real form; `gis_agent.py`'s `DATASET_TO_QUESTIONS`/`BRISTOL_LAYER_IDS` naming and `planning_agent.py`'s own `DATASET_TO_QUESTIONS` have deliberately NOT been touched | Per this roadmap's own standing rule, an architecture-affecting discovery gets flagged and held for confirmation before code already built around the old assumption gets changed — exactly the same discipline as the 2026-08-02 GIS-backend-split discovery earlier this sprint. The three modules (registry, gis_agent, planning_agent) are now internally inconsistent with each other on this one point until Griff confirms how to reconcile them — documented prominently in `con29_registry.py`'s own module docstring so this isn't lost between sessions |
| 2026-08-02 | Reassessed the Sprint 0 success criterion "CON29 registry contains all 28+ question groups" rather than silently forcing the real-form rebuild to hit that number | Griff's real exemplar supports 19 confirmed + 3 unconfirmed-numbering = 22 total top-level groups for CON29 Part 1 alone. The original "28+" figure appears to have been an estimate that didn't survive contact with the real form — reaching it may require CON29O (optional enquiries), a separate form this exemplar doesn't include. Flagged in the Sprint 0 checklist itself (marked `[~]`, not silently checked off) with the reasoning attached, rather than quietly padding the registry to hit a target that may itself need revising — same treatment as the Bristol-conservation-area criterion correction earlier this sprint |
| 2026-08-03 | RESOLVED the 2026-08-02 TPO/Article-4 flag: `gis_agent.py` and `planning_agent.py` corrected to match `con29_registry.py`'s real-form rebuild. TPO references changed "3.7" -> "3.9m" throughout both modules and their tests. Enforcement notices changed "1.1g" -> "3.9a". Article 4 moved out of both modules' `DATASET_TO_QUESTIONS` into a new `NON_CON29_DATASETS` dict (dataset name -> reason string) in each — still genuinely queried, just no longer claimed to answer a CON29 question | Confirmed with Griff before touching either already-built module, per this roadmap's own standing rule. `planning_agent.py`'s `get_planning_data()` was iterating `DATASET_TO_QUESTIONS` directly to decide what to fetch — moving Article 4 out of that dict would have silently stopped querying it, a real functional regression, not just a documentation fix. Introduced `ALL_DATASETS` (the union of `DATASET_TO_QUESTIONS` and `NON_CON29_DATASETS`) and pointed the query loop at that instead. `gis_agent.py` needed no equivalent fix — its per-dataset query calls were already hardcoded, not dict-iteration-driven, so moving Article 4's question-mapping there was a pure documentation change. 8 new/updated tests across `test_planning_agent.py` and `test_gis_agent.py`; 59/59 passing across the whole suite |
| 2026-08-03 | Corrected `scripts/tally_sprint1_coverage.py`'s own hardcoded group table (standalone "3.7" TPO group, "1.1h-i Article 4" group, mislabeled "3.6 Outstanding notices", nonexistent "3.2") to match the same real-form IDs — surfacing that the corrected tally is 8 architectural / 6 functional groups, down from the 10 / 8 reported at Sprint 1's closure. Sprint 1's own "at least 10 CON29 question groups for Bristol" success criterion, previously reported as met, **is no longer met** with the corrected IDs | This tally script doesn't import `con29_registry.py` directly — it hardcodes its own group table mirroring the roadmap's original (now-superseded) classification, so it didn't automatically pick up yesterday's registry rebuild and needed its own pass. The drop in group count is a correction to what the same real API calls were honestly claimed to answer, not a loss of functionality — no adapter's actual behaviour changed. Recorded here rather than silently lowering the test threshold to make it look unchanged; Sprint 1's closure claim itself may need revisiting with Griff as a separate conversation from continuing Sprint 2 |

---

## Troubleshooting Log

| Date | Issue | Resolution |
|---|---|---|
| 2026-07-22 | No self-serve API key exists for HMLR LLC1 — roadmap's `developer.hmlr.gov.uk` assumption was incorrect. Access is via Business Gateway, requiring an active Business e-services account and Basic Auth credentials, aimed at organisations already transacting with HMLR (conveyancers, lenders, software providers). | Unresolved — logged as a blocker in Current State. Likely path: law firm partner's existing account, or contact channelpartners@landregistry.gov.uk. Does not block other Sprint 0/1 work; only blocks the Bristol LLC1 adapter. |
| 2026-07-25 | Real curl test against OS Places API (run by Griff outside the Codespace, not by an agent) showed `output_srs` defaults to EPSG:27700 (British National Grid) — the response contained `X_COORDINATE`/`Y_COORDINATE` but no `LAT`/`LNG` field at all. `property_resolver.py`'s `_call_os_places_find` did not request `output_srs=WGS84`, so `resolve()` would have raised `ResolverServiceError` on every real address (mocked tests didn't catch this, since the fixtures were illustrative and already contained LAT/LNG). Also observed: free-text queries without a postcode risk a wrong match — "Bristol City Hall" matched Bristol Cathedral instead, `MATCH_DESCRIPTION: "NO MATCH"`, score 0.6. Adding the postcode raised both test queries to `MATCH_DESCRIPTION: "GOOD"` (0.9 and 0.8). | RESOLVED 2026-07-25: `output_srs=WGS84` added to the OS Places API request params. Real (non-illustrative) fixture responses captured for both Bristol ("122 Whiteladies Road, Bristol BS8 2RP") and Hackney ("14 Amhurst Road, London E8 1LL" — see next row) and dropped into `tests/fixtures/`. `match_score`/`match_description` added to `ResolvedProperty` — see Architecture Decisions. All 6 tests pass against the real fixtures. |
| 2026-07-25 | The real Hackney fixture capture surfaced a second issue, not a bug: the roadmap's own example address, "14 Amhurst Road, London E8 1LL" (used in the Evidence Manifest Schema section and elsewhere in this document), does not exist — number 14 isn't a real property on that street. OS Places API returned number 41 instead, the nearest genuine match on the same street/postcode, scored `MATCH_DESCRIPTION: "GOOD"` (0.8) despite being a different house number. | Not a defect to fix — a real limitation of address matching that `match_score`/`match_description` now make visible to callers instead of hiding. Action item: do not carry "14 Amhurst Road" forward as an assumed-real test property in Sprint 2's locked test set; it was always illustrative. The captured fixture (UPRN 10008231087, "41 Amhurst Road") is kept deliberately as a regression test for match-confidence surfacing, not as a stand-in genuine test property. |
| 2026-07-25 | Historic England layer discovery — flagged the real risk before it caused a silent failure: substring match assumed a space ("listed building"), and a separate points-vs-polygons layer split could mean discovery silently lands on the incomplete polygon layer (HE's own docs: only covers buildings listed/amended since April 2011). | Confirmed via real `?f=json` call 2026-07-25 (Griff): both "Listed Building points" (id 0) and "Listed Building polygons" (id 3) exist on this service — the risk was real, not hypothetical. `_discover_listed_building_layer_id` fixed to explicitly prefer the points layer, with two regression tests (including one with the array deliberately reordered) proving the choice no longer depends on list order. RESOLVED. |

---

## Project Log

| Date | Sprint | Entry |
|---|---|---|
| 2026-07-22 | — | v2.0 roadmap created. Major architecture revision. Previous v1.0 archived. Phase 0 not started. |
| 2026-07-22 | Sprint 0 | Work begins. OS Names API key already held. Added Codespaces/Colab-only development environment setup as the first block of Sprint 0's "What to build". Current State updated to IN PROGRESS. |
| 2026-07-25 | Sprint 0 | Reviewed uploaded Sprint 0 code (`property_resolver.py`, `con29_registry.py`, tests, fixtures). con29_registry.py: 51 question entries across all three buckets, compiles clean, no issues found. property_resolver.py: verified the two previously-flagged-uncertain planning.data.gov.uk query params against live docs — `local-authority-district` + `latitude`/`longitude` confirmed correct as written; `dataset=boundary` confirmed NOT to exist, removed (see Architecture Decisions & Changes). Added missing Hackney fixture + parity tests (Sprint 0 success criteria require both boroughs, only Bristol was covered). Added missing `.env.template`. Outstanding before Sprint 0 can be marked done: real (non-illustrative) fixture capture and a live pytest run inside the Codespace — not yet done anywhere, since the reviewing environment has no network access. |
| 2026-07-25 | Sprint 0 | Griff ran real curl calls against OS Places API outside the Codespace and pasted the results. Found and fixed a genuine bug: `output_srs=WGS84` was missing from the request, so real calls returned BNG X/Y with no LAT/LNG, which would have made `resolve()` raise on every real address. Fixed, 5/5 mocked tests still pass. Confirmed the free-text-without-postcode match-quality risk flagged earlier is real (weak/wrong match on a landmark name; strong match once postcode included). Two items raised but not yet resolved: (1) whether to add `match_score`/`match_description` to `ResolvedProperty` so weak matches aren't silently trusted, (2) real fixture capture still hasn't happened in a form where Claude has seen the raw JSON — only a prose summary of results exists so far. |
| 2026-07-25 | Sprint 0 | Griff pasted the raw JSON from re-run curl calls (with the output_srs fix). Added `match_score`/`match_description` to `ResolvedProperty`. Replaced the illustrative Bristol/Hackney fixtures with these real captured responses (Bristol: 122 Whiteladies Road, UPRN 67678, MATCH 0.9 GOOD; Hackney: 14 Amhurst Road query returned 41 Amhurst Road, UPRN 10008231087, MATCH 0.8 GOOD). Rewrote tests against the real fixtures, added a dedicated match-confidence regression test. All 6 tests pass. Corrected the stale "How the property resolver works" diagram and Sprint 0 checklists (OS Names → OS Places, polygon → point lookup, checked off genuinely-complete items). Confirmed "14 Amhurst Road" is the roadmap's own fictional example address, not a real property — flagged so it isn't carried forward into the Sprint 2 locked test set. Sprint 0 is close but not done: GitHub push/CI-green not yet confirmed, Google/Groq keys not yet obtained, registry group count (24) still short of "28+". |
| 2026-07-25 | Sprint 0 | Griff diagnosed and fixed a `git`/`cp` mistake independently (copied from the older, unpatched `sprint0` folder instead of the fixed `con29-sprint0-closed` one — first `git status` correctly showed no diff, second attempt from the right folder showed all 4 changed files). Committed and pushed to `brainsnog/MAS` on GitHub; GitHub Actions run confirmed green. Google AI Studio and Groq API keys obtained. **Sprint 0 closed.** Two known gaps carried forward deliberately rather than forced: registry question-group count (24 vs "28+" — needs the real CON29R form, due at Sprint 2 gate) and Gemini/Groq keys not yet exercised by real code (first genuine call is naturally Sprint 2 / Sprint 5). Sprint 0's own success criteria list updated to reflect this rather than being force-checked. |
| 2026-07-25 | Sprint 1 | Starting. Corrected the Planning Data Agent spec in this roadmap (Sprint 1 §C) to match the 2026-07-25 architecture decision already logged for the resolver: point-based (`latitude`/`longitude`) queries against planning.data.gov.uk, not polygon-based — the original spec still assumed `polygon_wkt`, which the resolver no longer produces. Flagged the HMLR adapter's blocked status again at the point of building it and proposed a graceful-degradation stub (`coverage_flag: "manual"` + `blocked_reason`) rather than skipping the adapter file entirely — awaiting confirmation before implementing. |
| 2026-07-25 | Sprint 1 | A (HMLR stub), B (Historic England), C (Planning Data Agent), D (Normalisation Layer) all built and tested — 33/33 passing. Agreed with Griff to defer B's one open item (layer-discovery verification) to a closing checklist rather than block C/D, since nothing else in Sprint 1 depended on it. Began working through the closing checklist systematically, one item at a time, as requested. |
| 2026-07-25 | Sprint 1 | Closing checklist item 1 (Historic England layer discovery) resolved. Griff ran the real `?f=json` call and pasted the full layer list. Confirmed the actual risk: both "Listed Building points" (id 0) and "Listed Building polygons" (id 3) exist on this service; the original code's choice of points was array-order luck, not a guarantee. Fixed to explicitly prefer the points layer, added two regression tests (including one with the layers deliberately reordered) proving the fix doesn't depend on list order. 35/35 tests pass across Sprint 0 + Sprint 1. Moving to closing checklist item 2 (GitHub push + CI green) next. |
| 2026-07-25 | Sprint 1 | Closing checklist item 2 confirmed by Griff — pushed to GitHub, green CI check seen. Closing checklist item 3 (tally CON29 question-group coverage) done programmatically via new `scripts/tally_sprint1_coverage.py`, locked in by `tests/test_tally_sprint1_coverage.py`: 10 groups architecturally covered (meets the "at least 10" criterion), 8 delivering real Bristol data today (the 2-group gap is 3.1/3.12, both correctly excluded for being HMLR-stub-blocked rather than unbuilt). 37/37 tests passing across Sprint 0 + Sprint 1 combined. **All three closing-checklist items resolved — Sprint 1 is formally closed.** Also fixed a document-hygiene issue found while updating this log: six Sprint 1 build entries had been misfiled under Troubleshooting Log instead of Architecture Decisions & Changes in earlier sessions — moved to the correct section, Troubleshooting Log restored to its legitimate 3 entries. Sprint 2 (GIS Agent & Document Agent) not yet started. |
| 2026-08-02 | Sprint 2 | Started Sprint 2 (GIS Agent). Flagged the same stale-spec pattern already seen twice before (resolver, planning_agent): Sprint 2 §A still assumed "does the property polygon intersect this layer?", which no longer holds. Griff confirmed the fix (point + per-feature-type buffer) before any code was written. Live-verified Bristol's and Hackney's actual GIS sources rather than trusting the roadmap's council names at face value — found Bristol on a legacy ArcGIS Server and, unexpectedly, Hackney on GeoServer/WFS entirely, not ArcGIS. Flagged as an architecture-affecting discovery and held for confirmation before building, per standing instructions. |
| 2026-08-02 | Sprint 2 | Griff found the real Hackney backend directly — inspected the config the public tree map loads client-side and found a GeoServer WFS `vectorTileUrl`, then pulled the real `GetCapabilities` document (~700 layers) and a real WFS `GetFeature` CSV export for the TPO layer. Combined with a real `?f=json` call against Bristol's INSPIRE MapServer (19 layers, pasted by Griff). Confirmed real layer IDs/typeNames for TPO and Article 4 on both boroughs, plus conservation area, brownfield register, and genuinely strong Part 2A contaminated-land layers on Hackney's side. Caught and avoided a near-miss: a same-named "INSPIRE MapServer" from a different council (City of London) surfaced in search results with different layer numbering — did not reuse it. Confirmed TPO buffer design with Griff: 15m radius, same shape as Historic England's existing pattern. Dropped flood zone from scope (not a CON29 field) with Griff's agreement. |
| 2026-08-02 | Sprint 2 | Built `src/agents/gis_agent.py` against the confirmed real endpoints/layer names — two backend functions (`_query_arcgis`, `_query_wfs`) behind one per-borough dispatcher. 12 new tests added (`tests/test_gis_agent.py`), network-mocked, same `httpx.MockTransport` pattern as the rest of the suite. 49/49 tests passing across Sprint 0-2 combined. Bristol's Rights of Way/Contaminated Land and Hackney's Rights of Way represented as explicit `unavailable_reason` stubs rather than silently omitted or invented — same treatment as the HMLR stub. Corrected Sprint 2's own success-criteria checklist rather than force-fitting: the "Bristol conservation area" criterion can't be met by this module as built (that field is already covered elsewhere, by `planning_agent.py`) — flagged `[~]`, not silently checked off. Document Agent (`pdf_extractor.py`, `llm_extractor.py`) and `session_store.py` — the rest of Sprint 2 — not yet started. Test property set still not locked with the law firm partner; remains a hard gate before Sprint 3. |
| 2026-08-02 | Sprint 0 (registry gap) | Griff shared the real St Albans CON29R/LLC1 exemplar (search ref A/2025/00248) that had been referenced but not yet attached in earlier sessions, plus a `schema.xsd` in response to last session's Hackney geometry-field-name ask. The schema call turned out inconclusive (a wrapper document with two unfollowed `xsd:import`s, not the field definitions themselves) — flagged, two ready-made follow-up URLs given to Griff, gap stays open; Griff opted to defer this and the Historic England/Gemini fixture-capture items to continue with the rest of the sprint. Rebuilt `src/con29_registry.py` from scratch against the real exemplar — full account in Architecture Decisions. Surfaced a genuine architecture-affecting discovery mid-rebuild (TPO is real-form 3.9(m) not 3.7; Article 4 has no standalone CON29 number) that contradicts what `gis_agent.py` and `planning_agent.py` were already built against — flagged prominently in the registry's own module docstring and held for confirmation, per this roadmap's standing rule, rather than silently propagated into the already-built adapters. Added `tests/test_con29_registry.py` (8 tests, 57/57 total across the suite) locking in the real-form fidelity so a future edit can't silently drift back toward guessed text. Reassessed the Sprint 0 "28+ question groups" target honestly rather than padding to meet it — see Architecture Decisions. |
| 2026-08-03 | Sprint 0 (registry gap), resolution | Griff confirmed resolving the TPO/Article-4 flag before continuing to Sprint 2 §B. Corrected `gis_agent.py` and `planning_agent.py` to match `con29_registry.py`'s real-form IDs: TPO "3.7" -> "3.9m" throughout; enforcement notices "1.1g" -> "3.9a"; Article 4 moved out of `DATASET_TO_QUESTIONS` into a new `NON_CON29_DATASETS` dict in each module (still queried, no longer claimed to answer a CON29 question). Fixed a real risk while doing so: `planning_agent.py`'s query loop iterated `DATASET_TO_QUESTIONS` directly, so moving Article 4 out would have silently stopped fetching it — introduced `ALL_DATASETS` and repointed the loop at that instead. Also corrected `scripts/tally_sprint1_coverage.py`'s own hardcoded group table, which had the same wrong IDs baked in independently of the registry — this surfaced that Sprint 1's own "at least 10 CON29 question groups" closure claim (reported 10/8, architectural/functional) no longer holds once corrected (now 8/6). Recorded as a real, honest regression in Architecture Decisions rather than adjusted quietly. 8 new/updated tests; 59/59 passing across the whole suite. Ready to move to Sprint 2 §B — Document Agent. |

---

## Key References

Read these before questioning any architectural decision.

- **Fox, J. (2026). arXiv:2605.26305** — Cellular RAG. Now scoped to Borough B PDF extraction only, not the primary pipeline.
- **Zhang et al. (2025). PARSE. arXiv:2510.08623** — Two-stage extraction. Applied in `llm_extractor.py`.
- **Dahl et al. (2024). arXiv:2405.20362** — Legal AI hallucination. Justifies `cited_text` mandatory field.
- **AgentHallu (2025). arXiv:2601.06818** — Agent hallucination taxonomy. Maps to conflict detection and error analysis.
- **HMLR (2026). LLC Programme** — Migration status. Bristol migrated (Gold), Hackney not migrated.
- **EIR Reg 5(1), Environmental Information Regulations 2004** — Legal basis for Bucket 3 request templates.
- **Pan & Wu (2025). arXiv:2511.01149** — MAS task decomposition. Justifies adapter-per-source pattern.
- **Surrey Heath CON29R EIR field map (2023)** — Definitive map of which CON29 fields have public EIR-accessible data.
