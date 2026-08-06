"""
CON29 output schema — WP-01. Blocks everything downstream (Sprint 3's mapper
onward); nothing before this imported it because it didn't exist.

`disposition` is the Section 5 four-state model (CON29_BUILD_HANDOFF.md
Section 5), which SUPERSEDES the roadmap's own `coverage_flag` field
(auto/agent_navigated/manual/unavailable) for this purpose. The two are
different axes: `coverage_flag`/`bucket` (still in con29_registry.py)
describes which *retrieval tier* a question is expected to use; `disposition`
describes what actually happened for one field on one real search. A bucket-1
(auto) question can still end up `unavailable` on a given search if its
source errored.

DEF-02 (`has_any()` conflating "queried, no record" with "the call failed")
is made unrepresentable here, not just fixed at the call site: a
`determinate_negative` field can never carry an `error`, and an `unavailable`
field always must. See `_disposition_error_consistency` below and
tests/test_models.py's strict-union / disposition tests.

`retrieved_at` / `search_timestamp` are `AwareDatetime`, not `str`. Tested
explicitly against pydantic==2.13.4 (as pinned) rather than assumed, per
CLAUDE.md's "verify before building" — see tests/test_models.py for the full
probe. Two things that behave differently, both load-bearing:

  - Construction (`CON29Field(retrieved_at=...)`) requires a real aware
    `datetime` object and rejects every string form, including an
    offset ISO-8601 string and the "...Z" suffixed format
    CON29_ROADMAP_v2.md's own Evidence Manifest Schema example uses. A naive
    `datetime` is rejected too (`AwareDatetime` requires tzinfo). Every
    caller building a CON29Field must construct a datetime, never format a
    timestamp string and pass that.
  - `model_validate_json` takes a different, documented Pydantic v2 path
    (JSON has no native datetime type) and DOES accept both offset and
    "...Z" suffixed ISO-8601 strings even under strict=True, while still
    rejecting a naive ISO string. A manifest written with `model_dump_json`
    therefore reads back cleanly with `model_validate_json`, even though the
    same string could never be used to construct a CON29Field directly.

`_serialise_as_z_suffixed_utc` matches the `...Z` format the roadmap's own
manifest schema example uses. Adapter dataclasses built before this file
existed (e.g. hmlr_llc1.LLC1Result.retrieved_timestamp) still hand back plain
`%Y-%m-%dT%H:%M:%SZ` strings internally — whether adapters should be moved to
emit aware datetime objects directly, now that a string can never reach this
model's constructor, is an open WP-02 question, not decided here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_serializer, model_validator

Disposition = Literal[
    "determinate_positive", "determinate_negative", "flagged_manual", "unavailable"
]
# "playwright" was considered and deliberately excluded, not overlooked: it
# has never been used, is in no work package, and Handoff Section 4 rules out
# the only sources (the two council planning portals) it would have targeted.
RetrievalMethod = Literal["api", "gis", "dataset", "html", "pdf_llm", "none"]
Confidence = Literal["HIGH", "MEDIUM", "LOW"]
Borough = Literal["bristol", "hackney"]


def _serialise_as_z_suffixed_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CON29Field(BaseModel):
    model_config = ConfigDict(strict=True)

    question_id: str
    question_text: str
    disposition: Disposition
    answer: bool | str | None = None
    answer_detail: Optional[str] = None
    confidence: Optional[Confidence] = None
    source_name: Optional[str] = None
    # Redacted before storage — see DEF-04 (WP-02, src/redaction.py — not
    # written yet). Never write a raw captured URL here.
    source_url: Optional[str] = None
    retrieved_at: Optional[AwareDatetime] = None
    cited_text: Optional[str] = None
    # No default: a field cannot be built without saying what happened
    # (disposition is required) or how (retrieval_method is required too).
    # "none" is still a valid value, for flagged_manual fields with no
    # retrieval attempt at all.
    retrieval_method: RetrievalMethod
    error: Optional[str] = None
    conflict_detected: bool = False
    conflict_note: Optional[str] = None

    @field_serializer("retrieved_at")
    def _serialise_retrieved_at(self, value: Optional[datetime]) -> Optional[str]:
        return _serialise_as_z_suffixed_utc(value) if value is not None else None

    @model_validator(mode="after")
    def _disposition_error_consistency(self) -> "CON29Field":
        if self.disposition == "determinate_negative" and self.error is not None:
            raise ValueError(
                "a determinate_negative field cannot carry an error — that is "
                "exactly the DEF-02 conflation this model exists to prevent"
            )
        if self.disposition == "unavailable" and self.error is None:
            raise ValueError(
                "an unavailable field must carry an error explaining why"
            )
        return self

    @model_validator(mode="after")
    def _cited_text_required_for_pdf_llm(self) -> "CON29Field":
        if self.retrieval_method == "pdf_llm" and self.cited_text is None:
            raise ValueError(
                "cited_text must be provided for all pdf_llm extractions"
            )
        return self


class PropertySearchResult(BaseModel):
    model_config = ConfigDict(strict=True)

    search_id: str
    property_address: str
    uprn: Optional[str]
    borough: Borough
    search_timestamp: AwareDatetime
    fields: list[CON29Field]
    coverage_summary: dict[str, int]
    overall_confidence: Literal["HIGH", "MEDIUM", "LOW", "INDETERMINATE"]
    conflicts_detected: int
    eir_requests_generated: int
    system_notes: list[str] = Field(default_factory=list)

    @field_serializer("search_timestamp")
    def _serialise_search_timestamp(self, value: datetime) -> str:
        return _serialise_as_z_suffixed_utc(value)
