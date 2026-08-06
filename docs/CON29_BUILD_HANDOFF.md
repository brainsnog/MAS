# CON29 Automated Search — BUILD HANDOFF

## Verified state, defect register, confirmed source catalogue, and work packages

**Version 1.0 — compiled 2026-08-05**
**Submission deadline: 2026-08-20**

---

> ## INSTRUCTION FOR CLAUDE CODE
>
> This document is the build-track authority. Read it before writing a line of code.
>
> It does not replace `CON29_ROADMAP_v2.md`. It supersedes that file in three specific places, each marked **SUPERSEDES** below, and it adds a confirmed source catalogue that did not previously exist. Everywhere else, the roadmap still governs.
>
> ### Rules that are non-negotiable
>
> 1. **Nothing in Section 3 was assumed. Every endpoint in it was queried live on 2026-08-05 and returned the payload described.** If you find a discrepancy, that is a real change in the source, not a documentation error. Record it in the Deviation Log and flag it. Do not silently adapt.
> 2. **Section 4 lists sources that must NOT be built against.** These are access-governance decisions, not technical obstacles. Do not implement a workaround, do not add a User-Agent header to defeat a challenge, do not ignore a `Disallow`. If a work package appears to require one of these, stop and flag it.
> 3. **Verify before building.** This project has repeatedly been saved by querying a source before writing an adapter for it, and repeatedly embarrassed when that step was skipped. Where this document says "unverified", it means unverified — query it first.
> 4. **Graceful degradation over omission.** Where a source is blocked or absent, the correct output is an explicit `DatasetResult.unavailable_reason` stub or a Bucket 3 classification, never a silently missing field.
> 5. Update the Project Log and Deviation Log in `CON29_ROADMAP_v2.md` at the end of every session.

---

## 1. Current verified state

Verified by execution 2026-08-05, sub-question figures re-verified 2026-08-06, not by reading documentation.

```
Test suite:        59 passed in 0.31s
Registry:          63 sub-questions across 19 confirmed top-level groups
                   39 auto / 24 agent_navigated / 0 manual
                   + 3 entries in UNCONFIRMED_NUMBERING (excluded from all metrics)
Coverage tally:    8 architectural / 6 functional groups — prints "NOT MET"
Sub-question wiring: 18 of 63 architecturally wired (29%)
                     12 of 63 functional after the HMLR block (19%)
                     (the two counts differ by the four rights-of-way IDs
                     2.2-2.5, which are wired to explicit unavailable_reason
                     stubs rather than a live source. See
                     scripts/verify_section1.py and the 2026-08-06 Deviation
                     Log entry.)
```

### What exists and works

| Component | State |
|---|---|
| `src/resolver/property_resolver.py` | Working. OS Places UPRN resolution. |
| `src/adapters/hmlr_llc1.py` | Graceful-degradation stub. Business Gateway access blocked. |
| `src/adapters/historic_england.py` | Working. Open access, no key. Dynamic layer discovery. |
| `src/agents/planning_agent.py` | Working. planning.data.gov.uk national datasets. |
| `src/agents/gis_agent.py` | Built, **not integrated**. See DEF-01. |
| `src/normalisation/normaliser.py` | Working, **incomplete**. See DEF-01. |
| `src/con29_registry.py` | Rebuilt against real CON29R form wording. Authoritative. |
| `scripts/tally_sprint1_coverage.py` | Working, **measures the wrong thing**. See Section 5. |

### What does not exist

- `src/models.py` — `CON29Field` and `PropertySearchResult` exist only as prose in the roadmap. **This is work package WP-01 and blocks everything downstream.**
- Everything from Sprint 2 §B onward: document agent, extraction, mapping, confidence, validation, EIR generation, evidence manifest, report, orchestrator, CLI.

### Repository state

**The GitHub repository is materially behind local work.** It does not contain `gis_agent.py`, the rebuilt `con29_registry.py`, `scripts/`, or the associated tests. Push before starting. Claude Code works from the repository.

Three scaffolding issues:

- `requirements.txt` pulls `geopandas`, `shapely`, `pyproj`. Nothing imports them.
- `.github/workflows/tests.yml` installs a hand-picked dependency list rather than `requirements.txt`. Green CI will stop meaning what it appears to mean once the LLM extractor lands.
- `README.md` is a stub.

---

## 2. Sprint 1's failed criterion — resolution

**SUPERSEDES** the Sprint 1 success criteria in `CON29_ROADMAP_v2.md`.

The criterion "at least 10 CON29 question groups covered for Bristol" was measured against a registry that was subsequently found to be wrong. When `con29_registry.py` was rebuilt against genuine CON29R form wording, the measuring stick changed. **No adapter's behaviour changed.** Same endpoints, same calls, same data.

The criterion cannot be recovered within Sprint 1's scope, because the groups that disappeared (standalone 3.7, Article 4 as a top-level CON29 group) do not exist on the real form.

**Decision: retire the criterion as invalid by construction. Do not reopen Sprint 1.** Sprints 0 and 1 remain closed. Replace with the metric in Section 5.

This is a genuine methodological finding — measuring against an unvalidated proxy schema, caught by contact with the real artefact — and belongs in the write-up rather than being buried.

---

## 3. Confirmed source catalogue

**Every endpoint below was queried live on 2026-08-05 and returned the payload described.**

Test point used throughout: The Pineapple, 37 St Georges Road, Bristol BS1 5UU (`-2.604062, 51.452073`).

### 3.1 Bristol — `maps2.bristol.gov.uk/server2/rest/services/ext`

The server catalogue was enumerated. It hosts **over 100 services**. `gis_agent.py` currently queries exactly one of them (`ext/INSPIRE`).

**Critical warning:** this is a shared regional estate, not Bristol-only. It hosts `banes_hist`, `devon_edit`, `glo_hist`, `nsom_hist`, `som_hist`, `wilts_her`, `worcester_city`, and multiple South Gloucestershire (`sgc_`) services. Every layer adopted must have its provenance confirmed and results spatially constrained to Bristol, or the system will return neighbouring-authority data against a Bristol address. This is the same failure class as the City of London INSPIRE near-miss already recorded in the roadmap's Architecture Decisions table.

| CON29 | Service / Layer | Key fields | Status |
|---|---|---|---|
| 1.1(a)–(f) planning history | `ll_environment_and_planning` layer 2 "Planning applications" | `REFVAL`, `ADDRESS`, `PROPOSAL`, `STATUS`, `DECISION`, `DEC_DATE` | **CONFIRMED.** 15 features at `distance=0`, all subject property. |
| 1.2 / 3.11 conservation area | `ODP_Datasets` layer 5 "Conservation area dataset" | `REFERENCE`, `NAME`, `DESIGNATION_DATE`, `DOCUMENT_URL`, `DOCUMENTATION_URL` | **CONFIRMED.** Returned CA10 "Park Street and Brandon Hill". |
| Document feed | `ODP_Datasets` layer 4 "Conservation area documents" | `DOCUMENT_URL`, `DOCUMENT_TYPE` (`area-appraisal`) | **CONFIRMED.** Live URL on `bristol.gov.uk/files/`. |
| 2.2–2.5 rights of way | `ll_transport` layer 0 "Public Rights of Way" | `ROUTE_CODE`, `STATUS` (`FP`), `LEGAL_TYPE` | **CONFIRMED.** Returned `BCC/391/10`, status `FP`. Closes a KNOWN GAP. |
| 2.1 adopted highway | `Map` layer 0 `ADOPTED_HIGHWAY_DUMMY` | `ADOPTION_STATUS`, `CLASS` (12 codes incl. Section 38, Prospectively Maintainable, Private, Stopped Up), `TYPE`, `USRN`, `DATE_OF_ADOPTION` | **POPULATED, ACCESS PATTERN UNRESOLVED.** See DEF-08. |
| 3.6 roads and traffic | `ll_transport` layers 54–58 (LSG Dedications/Designations/Interests/Reinstatements/Road numbers), 33 Road works, 50 Speed limits, 43 Twenty mph zones | `USRN`, `STREET_NAME`, `DESIGNATION_NAME` | **CONFIRMED SCHEMA.** Returned Traffic Sensitive, Winter Maintenance, Speed limits for St Georges Road. Mapping to sub-questions not yet done. |
| 3.13 contaminated land | **NONE** | — | **EVIDENCED ABSENCE.** See 3.3. |

**Also present, not yet assessed:** `ODP_Datasets` layers 0–3 and 6–7 (TPO, TPO zone, listed building outline, Article 4), `ll_environment_and_planning` layer 9 Article 4 Directions, 52 Conservation Areas, 59 Environmental Permits, 60 Petroleum storage certificates, 20 S106 agreements, 30/31 TPO canopy and trunk.

**Do not use `ext/pollution` for 3.13.** Its three layers are Industrial Pollution Inventory (radioactive waste, substances, waste transfers) — a legacy emissions inventory of industrial sites, not Part 2A contaminated land designations. Mapping it to 3.13 would produce a false positive with legal consequences on a property transaction.

**Do not use `ext/LSG_STREET_LOCATOR` for 2.1.** It is a geocoder (`Geocode,ReverseGeocode`) with a single `SingleKey` field. It carries no adoption status. It has a legitimate secondary use: reverse-geocoding easting/northing to an abutting street name, which is what Hackney's enforcement register requires as `street_description`. Note `spatialReference.wkid` is `null` and must be confirmed empirically.

**Do not use `ext/moving_home`.** Despite the name, it is a public amenity map (bus stops, GPs, libraries). It answers no CON29 question. Its `fullExtent` is an uninitialised default spanning roughly -5,220,000 to 6,020,000 in EPSG:27700, so per-layer verification is required for anything in that service.

### 3.2 Bristol — source precedence

Conservation Areas appears in **five** places: `ll_environment_and_planning` (52), `datagov` (196), `ODP_Datasets` (5), `historic` (16), and planning.data.gov.uk. Listed buildings appears in four.

**Ruling: `ODP_Datasets` is authoritative for Bristol borough-level designations.** Its field names (`reference`, `document-url`, `document-type`, `entry-date`, `start-date`, `end-date`) are the MHCLG Open Digital Planning schema, making it Bristol's own ODP publication set. Precedence:

1. `ODP_Datasets` — Bristol's authoritative ODP extract
2. `historic` — Historic Environment Record, for locally listed assets national datasets do not carry (layer 31 "Local List")
3. planning.data.gov.uk — national cross-check
4. All others — ignore

Where sources disagree, that is a genuine cross-source conflict and is the validation agent's job. **These are the project's first real conflict test cases.** Capture them rather than resolving them silently.

### 3.3 Bristol contaminated land — evidenced absence

Seventeen services enumerated (fifteen via loop, plus INSPIRE and pollution individually). No Part 2A register, no contaminated land designation layer anywhere on the estate.

Meanwhile Hackney's GeoServer publishes two Part 2A layers.

**This is a finding, not a gap.** The high-digital-maturity borough is the one with the hole. Classify Bristol 3.13 as Bucket 3 with an EIR template, and cite the enumeration as evidence.

### 3.4 Hackney

| CON29 | Source | Status |
|---|---|---|
| 3.13 contaminated land | GeoServer WFS, two Part 2A layers | Built in `gis_agent.py`. `HACKNEY_GEOM_FIELD = "geom"` **still unverified** — see DEF-06. |
| 1.2 / 3.11 conservation area | GeoServer WFS | Built, not integrated (DEF-01). |
| Brownfield register | GeoServer WFS | Built, not integrated (DEF-01). |
| 2.2–2.5 rights of way | Exhaustive search of ~700 WFS layers found none | **CONFIRMED ABSENT.** Existing stub is correct. |
| Planning register | `developmentandhousing.hackney.gov.uk/planning/` | **BLOCKED — see Section 4.** |
| Enforcement register | `developmentandhousing.hackney.gov.uk/registers/` | **BLOCKED — see Section 4.** |
| Building control | No public register found; chargeable "property information enquiry" only | Bucket 3. |

### 3.5 National sources

| Source | Status |
|---|---|
| OS Places API | Working. **60-day trial started 2026-07-25, expires ~2026-09-23.** Fine for submission; may expire before the viva. |
| Historic England | Working, open access. |
| planning.data.gov.uk entity API | Working. Article 4, listed building, conservation area, brownfield-land, enforcement-notice, TPO. |
| planning.data.gov.uk `planning-application` dataset | **CONFIRMED USELESS FOR THIS PROJECT.** Bristol (entity 66) returns `count: 0`. Hackney (entity 163) returns `count: 0`. The only supplier found is Doncaster (109), whose records carry empty `geometry`, empty `point`, and no address field. Do not pursue. |
| HMLR Business Gateway | Blocked. Stub remains correct. |

### 3.6 Bristol building control

An FOI response records Bristol City Council stating it holds no online register of Building Control applications, with records viewable at their office by appointment. **The response is dated 2018 and needs a freshness check before it is cited.** Nothing found in 2026 sources contradicts it. Treat 1.1(j)–(l) as Bucket 3 for both boroughs pending that check.

---

## 4. Access governance — sources that must NOT be built against

**SUPERSEDES** the roadmap's assumption that council planning registers are an available Bucket 2 tier.

| Domain | Finding | Verified |
|---|---|---|
| `pa.bristol.gov.uk` (planning portal) | `robots.txt`: `User-agent: * / Disallow: /` — blanket, no carve-outs | 2026-08-05 |
| `developmentandhousing.hackney.gov.uk` (planning + registers) | `robots.txt`: `User-agent: * / Disallow: /`, **and** AWS WAF returns HTTP 202 with `x-amzn-waf-action: challenge` to non-browser requests, **and** the portal states it is geo-restricted outside the UK | 2026-08-05 |

**Neither borough has a permitted automated route to its planning register.** Do not implement HTML adapters against either. Do not defeat the WAF challenge. Do not spoof a User-Agent to bypass a block.

The form structures captured during discovery (Hackney's `SiteAddress[magic]` POST payload, the `fa=enforcement_register_search` dispatcher) are retained as **evidence for why these are Bucket 3**, not as implementation specifications.

### Permitted routes

| Domain | robots.txt | Constraint |
|---|---|---|
| `www.bristol.gov.uk` | Joomla default. Framework dirs, `/api/`, query-string article URLs disallowed. General content permitted. | **`Crawl-delay: 10` — must be implemented as a real rate limiter, not a comment.** No `sitemap.xml` (404). |
| `www.hackney.gov.uk` | Drupal default. `/admin/`, `/user/`, **`/search/` and `/search?`** disallowed. General content permitted. Footer states OGL v3.0. | Site search disallowed, so document discovery must use `sitemap.xml` (confirmed present, 979 URLs). |
| `maps2.bristol.gov.uk` | No `robots.txt` served (two attempts, HTTP/2 and HTTP/1.1, no response). Data published on data.gov.uk under OGL. | Attempt documented. Proceed. |

### Consequence for the document agent

**SUPERSEDES** the roadmap's assumption that the document agent retrieves from council planning portals.

The document agent's feed is **council-published policy and designation documents on the main council domains**, discovered via GIS `DOCUMENT_URL` fields and sitemaps. Confirmed working for Bristol conservation area appraisals. These are the documents several CON29 answers actually turn on.

**Open item:** the Hackney equivalent has not been confirmed. Check whether Hackney's GeoServer conservation area layer carries a document URL attribute, and check `hackney.gov.uk/sitemap.xml` for conservation area appraisals.

### Outstanding action

Permission-request emails to both councils were agreed but not confirmed sent. Send them, and record the date and any response. A documented refusal is a finding; an unasked question is a gap.

---

## 5. The coverage metric

**SUPERSEDES** the coverage targets in `CON29_ROADMAP_v2.md` (Bristol ~65%, Hackney ~40–45%) and the metric in `scripts/tally_sprint1_coverage.py`.

### Why the old metric fails

It counts **top-level groups**, so a group with fourteen sub-questions counts as "covered" when two are reachable. It also does not include `gis_agent.py` at all. It overstates coverage by roughly a factor of three.

### Replacement

**Denominator: all 63 sub-question IDs in `CON29_REGISTRY`.** State explicitly that the 3 `UNCONFIRMED_NUMBERING` entries and all of CON29O are excluded.

**Every field resolves to exactly one of four disjoint states:**

| State | Meaning |
|---|---|
| `determinate_positive` | A source was queried successfully and returned a record. |
| `determinate_negative` | A source was queried successfully and returned no record. **This is a real CON29 answer of "None", not a failure.** |
| `flagged_manual` | No permitted automated source exists. EIR template generated. |
| `unavailable` | A source should have answered but errored, was blocked, or timed out. |

**Two headline figures, both reported, split by borough:**

1. **Automated determination rate** = (`determinate_positive` + `determinate_negative`) / 63
2. **Correct disposition rate** = fraction of fields whose assigned state matches what the field actually merits

The second is the one that matters. It can approach 100% while the first sits at 19%, and it is the honest measure of whether the architecture works. "The system determines 19% and correctly escalates the remaining 81% with a legal basis attached, and the determinable fraction differs measurably between boroughs" is a defensible claim. "We automate 65%" was never going to be one.

Treat the roadmap's 65% and 40–45% as **hypotheses the evaluation revised**, not as targets that were missed.

---

## 6. Defect register

Severity: **S1** blocks other work or produces legally incorrect output. **S2** correctness or provenance. **S3** hygiene.

---

### DEF-01 — GIS results never reach `PropertyRecord` — S1

`normaliser.normalise()` accepts `llc1`, `historic_england`, `planning`. It does not accept `GisDataResult`. Everything `gis_agent.py` retrieves — Hackney conservation area, Part 2A contaminated land, brownfield register, both boroughs' TPO — has nowhere to land.

**Fix:** add a `gis: GisDataResult | None` parameter and merge into `PropertyRecord` under the precedence rules in Section 3.2.

**Acceptance:** a test asserting that a Hackney fixture with a Part 2A hit produces a `PropertyRecord` with contaminated land populated. Currently impossible to express.

---

### DEF-02 — `has_any()` conflates error with absence — S1

`PlanningDataResult.has_any()` and `GisDataResult.has_any()` both return `False` for "queried successfully, no features" and for "the call errored". A mapper using them treats a failed Hackney WFS call as a confirmed legal negative.

This is the silent false negative path, and it is distinct from the `HACKNEY_GEOM_FIELD` issue.

**Fix:** replace with a tri-state returning `positive` / `negative` / `error`, mapping directly onto the Section 5 states.

**Acceptance:** a test asserting that a `DatasetResult` carrying an `error` never produces `determinate_negative`.

---

### DEF-03 — `ResolvedProperty` discards required data — S1

Missing: `borough`, `search_id`, and the OS Places address components (`BUILDING_NUMBER`, `SUB_BUILDING_NAME`, `BUILDING_NAME`, `THOROUGHFARE_NAME`, `POST_TOWN`), which are present in the API response and thrown away in favour of the concatenated `ADDRESS` string.

There is also **no mapping anywhere from `local_authority_code` to the `Borough` literal**, and no rejection path for out-of-scope addresses.

**Fix:** add the fields, add a `local_authority_code → Borough` resolver, and raise a typed error for addresses outside Bristol and Hackney.

**Acceptance:** a test asserting a Manchester address is rejected with a clear error rather than silently processed.

---

### DEF-04 — Evidence manifest is not buildable — S1

Only `hmlr_llc1.py` records a retrieval timestamp. No agent captures the resolved request URL.

**Security constraint:** the OS Places URL carries the API key as a query parameter. Naive URL capture would write a live credential into an evidence manifest destined for a dissertation appendix. **URLs must be redacted before storage.**

**Fix:** add `retrieved_at` and `source_url` to `DatasetResult`; redact query-string credentials at capture time.

**Acceptance:** a test asserting no captured `source_url` contains the OS Places key.

---

### DEF-05 — `DEFAULT_BUFFER_METRES` produces false positives — S1

`gis_agent.py` applies a single hardcoded buffer to all layers. Confirmed live: a 50m buffer on Bristol planning applications returned four neighbouring properties alongside the subject; `distance=0` returned only the subject. The same applied to conservation areas (two areas at 50m, one at 0m).

Reporting a neighbour's planning history on a CON29 is a false positive with legal consequences.

**Fix:** buffer distance becomes a per-layer configuration value with a documented justification. Zero for site-specific polygons. Non-zero only where proximity is genuinely the question.

**Acceptance:** the Bristol planning applications query at `distance=0` returns only subject-property references.

---

### DEF-06 — `HACKNEY_GEOM_FIELD` unverified — S2

Still `"geom"`, still unconfirmed against the WFS schema. Failure mode is a caught exception recorded in `error`, so it is not silent **provided DEF-02 is fixed first**. Until then it is a silent false negative.

**Fix:** extract the real field name from the WFS `DescribeFeatureType` response.

---

### DEF-07 — WFS 2.0 parameter mismatch — S2

`_query_wfs` sends `version=2.0.0` with `typeName` (singular, the WFS 1.x parameter). WFS 2.0 uses `typeNames`. GeoServer is often lenient. Also unverified: the `SRID=4326;POINT()` EWKT CQL filter, and metre-unit `DWITHIN` against a natively 27700 layer.

**No Hackney WFS call has ever been made by this code.** Three untested assumptions are stacked here.

**Fix:** verify with one live call before trusting any Hackney result.

---

### DEF-08 — Adopted highway requires USRN-keyed access — S2

`Map/MapServer/0` is populated with confirmed adoption data, but point-in-polygon returned **Deanery Road** for a property fronting **St Georges Road**. `AREA_CALC` (655) disagrees with `SHAPE.STArea()` (89,955), suggesting multipart or coarse geometry. `DATE_OF_ADOPTION` was null.

CON29 2.1 asks about the highway *abutting* the property.

**Fix:** resolve the property's USRN (via `ll_transport` layer 49 LSG or `LSG_STREET_LOCATOR` reverse geocode), then query adoption by USRN. Do not use point-in-polygon.

**Also:** the layer is named `ADOPTED_HIGHWAY_DUMMY` and `QUERY_STATUS` carries an "Under Review" code. Record both as data-quality caveats. If USRN-keyed access cannot be made reliable, 2.1 is Bucket 3 for Bristol — an acceptable outcome, and better than a wrong answer.

---

### DEF-09 — Inconsistent error contract — S2

`historic_england.get_listed_building_status()` raises `HistoricEnglandServiceError`. `planning_agent`, `gis_agent` and `hmlr_llc1` never raise. `property_resolver` raises.

**Fix:** document one contract and apply it. Recommended: adapters never raise, they return a result carrying `error`. The resolver may raise, since it is a precondition.

---

### DEF-10 — Registry has no Bucket 3 — S2

`by_bucket("manual")` returns an empty list. The EIR generator has nothing to generate.

**Fix:** reclassify per Sections 3 and 4. At minimum: Bristol 3.13, both boroughs 1.1(j)–(l), Hackney 3.9(a) enforcement, and anything Section 4 blocks.

**Acceptance:** `by_bucket("manual")` returns a non-empty list, and every entry has a documented reason and a named request route.

---

### DEF-11 — Data quality traps — S3

Each needs a normalisation helper and a test:

- Bristol `ADDRESS` uses `\r` as a line separator.
- Bristol rights of way returns `" "` (whitespace) rather than `null` for absent `LEGAL_TYPE`, `EASTING`, `NORTHING`.
- `ODP_Datasets` `GEOMETRY` is WKT in a 2048-character string field, **truncated mid-coordinate**. Ignore it; use the real shape.
- Rights of way `STATUS` is an abbreviation code (`FP`, and presumably `BR`, `BOAT`, `RUPP`) requiring `terminology_map.py` entries.
- Bristol planning `STATUS`/`DECISION` vocabulary requires mapping: `GRANTED subject to condition(s)`, `REFUSED`, `Application Withdrawn`, `Application CANCELLED`, `Application Returned`, `Application Invalid On Receipt`, `Condition application decided`, `Deemed approval`, `Preservation Order NOT REQUIRED`.
- `REFVAL` suffixes classify application type: `/F` full, `/H` householder, `/LA` and `/LB` listed building, `/ADV` advertisement, `/COND` condition discharge, `/NMA` non-material amendment, `/VC` tree in conservation area, `/VP` TPO tree. **`/VC` and `/VP` must not be reported under 1.1.**

---

### DEF-12 — Scaffolding — S3

- Push local work to GitHub before anything else.
- Remove unused `geopandas`, `shapely`, `pyproj` from `requirements.txt`.
- Point CI at `requirements.txt`.
- No retry, backoff, structured logging, or per-call latency capture anywhere. Latency must be instrumented **now**, not retrofitted, because Sprint 5 reports on it.

---

## 7. Work packages

Ordered by dependency. Every acceptance criterion is written to be checkable programmatically.

### WP-01 — `src/models.py` — blocks everything

`CON29Field` and `PropertySearchResult` as strict Pydantic v2 models. `CON29Field` carries the four-state disposition from Section 5, `cited_text` mandatory with retry-on-null, `source_url` (redacted), `retrieved_at`, `confidence`, `retrieval_method`.

Note: `answer: bool | str | None` under Pydantic v2 strict mode has union-coercion pitfalls. Test explicitly.

**Accept:** models import; a field cannot be constructed in a state that is both `determinate_negative` and carrying an `error`.

### WP-02 — Defect sweep: DEF-02, DEF-03, DEF-04, DEF-09

The correctness foundation. Do these together; they touch the same dataclasses.

**Accept:** all four acceptance tests above pass. Existing 59 tests still pass.

### WP-03 — Wire the GIS agent: DEF-01, DEF-05, DEF-06, DEF-07

Includes the first live Hackney WFS call.

**Accept:** Hackney fixture with Part 2A hit produces a populated `PropertyRecord`. Bristol planning query at `distance=0` returns only subject-property references.

### WP-04 — Bristol source expansion

Add, per Section 3.1: `ll_environment_and_planning` layer 2 (planning history), `ODP_Datasets` layers 0–7 (TPO, listed building, conservation area, Article 4, documents), `ll_transport` layer 0 (rights of way). Implement Section 3.2 precedence. Capture conflicts rather than resolving them silently.

**Accept:** the test property returns CA10 with a resolvable `DOCUMENT_URL` and 15 planning references, all subject-property.

### WP-05 — Registry reclassification: DEF-10

**Accept:** `by_bucket("manual")` non-empty; every entry has a reason and a request route.

### WP-06 — Coverage metric rewrite

Replace `tally_sprint1_coverage.py` with the Section 5 metric.

**Accept:** reports both figures, split by borough, against a denominator of 63.

### WP-07 — Document agent

Feed is council-published documents per Section 4, **not** planning portals. Bristol rate limiter at 10 seconds is a hard requirement.

**Accept:** downloads and extracts text from the CA10 character appraisal. A test asserts the rate limiter delays consecutive `bristol.gov.uk` requests by at least 10 seconds.

### WP-08 — LLM extraction layer

Gemini 2.5 Flash, strict schema, `cited_text` mandatory. Scope stays narrow: PDF field extraction, terminology normalisation, conflict interpretation. Nothing else.

### WP-09 — Mapper, confidence scorer, validator, EIR generator

The validator now has real conflict cases from WP-04.

### WP-10 — Evidence manifest, report, orchestrator, CLI

`orchestrator.run_search()` must be a single callable with a serialisable return, so a Gradio UI can be added post-submission without touching the pipeline.

### WP-11 — Test property set and evaluation

Selection protocol: derive each property from the authoritative dataset defining its characteristic, so every address is real by construction. Select the characteristic from a source **independent** of the one the system queries, or the evaluation is circular. Include at least one property with a known characteristic the system cannot see, to test honest escalation.

Ground truth is **documentary**: fields with a hand-checkable authoritative public record. Everything else is marked unverifiable and excluded from the accuracy denominator, reported separately. Scope to roughly 15 checkable fields; 10 × 63 is 630 annotations and will not happen.

### WP-12 — Model comparison

Gemini 2.5 Flash vs Qwen 3 8B vs Llama 3.1 8B, 20 documents, 5–6 extraction fields. Corpus comes from WP-07.

### WP-13 — Hardening

Retries, backoff, structured logging, README, tag `v1.0.0-poc`.

---

## 8. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Document agent corpus depends entirely on council-published policy documents, a route confirmed for Bristol only | High — WP-08 and WP-12 both depend on it | Confirm the Hackney equivalent early in WP-07. If absent, the corpus is Bristol-weighted and that must be stated as a limitation. |
| Hackney WFS has never been called by this code | High — three untested assumptions in DEF-07 | First live call is the opening act of WP-03, not a later validation step. |
| Adopted highway may not be reliably USRN-resolvable | Medium | Timebox. If it does not resolve cleanly, 2.1 goes Bucket 3 for Bristol. |
| Shared regional GIS estate returns neighbouring-authority data | High — legally wrong output | Every adopted layer needs provenance confirmation and spatial constraint to Bristol. |
| OS Places trial expires ~2026-09-23 | Low for submission, medium for viva | Note it. Renew or budget before the viva. |
| Bristol building control FOI evidence is from 2018 | Medium — a citation freshness issue | Re-check before it is cited. |
| Codespaces intermittently firewalled | Medium — reproducibility claims | Local venv is already in use. Either support it formally and document secret handling, or resolve the firewall. Do not let it stay informal. |

---

## 9. Decisions still required

These are the user's, not Claude Code's. Flag rather than assume.

1. **Section 3.2 source precedence (ODP first).** Evidence-backed but not confirmed by the user.
2. **Bristol 2.1 fallback.** If USRN-keyed adoption does not resolve cleanly, confirm Bucket 3 is acceptable.
3. **Permission emails to both councils.** Agreed, not confirmed sent.
4. **Local execution environment.** Formally supported, or worked around?

---

## 10. Deviation log

| Date | Work package | Issue | Resolution |
|---|---|---|---|
| 2026-08-06 | Verification (pre-WP-01) | Section 1's "14 of 63 architecturally wired" was an arithmetic error — the functional adjustment (subtracting the four rights-of-way stub IDs 2.2-2.5) had been applied to the architectural count too. Rights of way IS architecturally wired: `gis_agent.DATASET_TO_QUESTIONS` maps it, and the explicit `unavailable_reason` stub is the graceful-degradation pattern this project mandates, not an absence of wiring. | Corrected Section 1 to 18 of 63 (29%) architecturally wired; functional stays 12 of 63 (19%). Derivation is in `scripts/verify_section1.py`, re-runnable rather than a one-off check. |
