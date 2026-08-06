"""
Tests for src/models.py (WP-01).

Includes explicit strict-mode behaviour probes for pydantic==2.13.4 (as
pinned in requirements.txt) rather than assuming documentation, per
CLAUDE.md's "verify before building". Two things were tested and found to
differ from an initial (wrong) assumption in models.py's docstring, which
was corrected once this evidence existed:

  1. AwareDatetime under strict mode, via the Python constructor
     (`CON29Field(retrieved_at=...)`), rejects every string form — an
     offset ISO-8601 string, a "...Z" suffixed string (the manifest
     format), and a naive ISO string are all rejected. Only a real aware
     `datetime` object validates, and a naive `datetime` object is also
     rejected. There is no "practical exception" for strings here.

  2. `model_validate_json` (JSON parsing mode) takes a genuinely different
     path and DOES accept both the offset and "...Z" ISO-8601 string forms
     even under strict=True — this is documented Pydantic v2 behaviour
     specific to JSON parsing (JSON has no native datetime type), not a
     bug. A naive ISO string is still rejected in this path too. This
     means an evidence manifest written with `model_dump_json` can be read
     back with `model_validate_json`, even though the same string could
     never be used to *construct* a CON29Field directly in Python — see
     `test_manifest_round_trip_via_json_survives_even_though_the_python_constructor_would_reject_the_same_string`
     below.
"""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.models import CON29Field, PropertySearchResult

# Realistic-length UPRN (12 digits is the practical maximum for a UK UPRN;
# real ones vary in length but are not 5 digits) — a short fabricated-looking
# value here is the same pattern flagged in the resolver's now-deleted
# "reference": "bristol" mock.
_REALISTIC_UPRN = "100023336956"


def _aware(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def _field(**overrides) -> dict:
    base = dict(
        question_id="3.5",
        question_text="Listed buildings.",
        disposition="determinate_positive",
        retrieval_method="api",
    )
    base.update(overrides)
    return base


# --- retrieved_at: AwareDatetime strict-mode behaviour, Python constructor -

def test_retrieved_at_accepts_an_aware_datetime():
    field = CON29Field(**_field(retrieved_at=_aware(2026, 8, 6, 12, 0, 0)))
    assert field.retrieved_at == _aware(2026, 8, 6, 12, 0, 0)


def test_constructor_rejects_an_offset_iso_string():
    with pytest.raises(ValidationError):
        CON29Field(**_field(retrieved_at="2026-08-06T12:00:00+00:00"))


def test_constructor_rejects_a_z_suffixed_string_even_though_thats_the_manifest_format():
    with pytest.raises(ValidationError):
        CON29Field(**_field(retrieved_at="2026-08-06T12:00:00Z"))


def test_retrieved_at_rejects_a_naive_datetime():
    with pytest.raises(ValidationError):
        CON29Field(**_field(retrieved_at=datetime(2026, 8, 6, 12, 0, 0)))


def test_constructor_rejects_a_naive_iso_string():
    with pytest.raises(ValidationError):
        CON29Field(**_field(retrieved_at="2026-08-06T12:00:00"))


def test_constructor_rejects_a_non_datetime_string():
    with pytest.raises(ValidationError):
        CON29Field(**_field(retrieved_at="yesterday"))


def test_retrieved_at_serialises_to_the_manifest_z_suffixed_format():
    field = CON29Field(**_field(retrieved_at=_aware(2026, 8, 6, 12, 0, 0)))
    assert field.model_dump(mode="json")["retrieved_at"] == "2026-08-06T12:00:00Z"


# --- retrieved_at: JSON parsing mode differs from the Python constructor ---

def test_model_validate_json_accepts_a_z_suffixed_string_where_the_constructor_would_reject_it():
    payload = '{"question_id": "3.5", "question_text": "Listed buildings.", ' \
              '"disposition": "determinate_positive", "retrieval_method": "api", ' \
              '"retrieved_at": "2026-08-06T12:00:00Z"}'
    field = CON29Field.model_validate_json(payload)
    assert field.retrieved_at == _aware(2026, 8, 6, 12, 0, 0)


def test_model_validate_json_accepts_an_offset_iso_string():
    payload = '{"question_id": "3.5", "question_text": "Listed buildings.", ' \
              '"disposition": "determinate_positive", "retrieval_method": "api", ' \
              '"retrieved_at": "2026-08-06T12:00:00+00:00"}'
    field = CON29Field.model_validate_json(payload)
    assert field.retrieved_at == _aware(2026, 8, 6, 12, 0, 0)


def test_model_validate_json_still_rejects_a_naive_iso_string():
    payload = '{"question_id": "3.5", "question_text": "Listed buildings.", ' \
              '"disposition": "determinate_positive", "retrieval_method": "api", ' \
              '"retrieved_at": "2026-08-06T12:00:00"}'
    with pytest.raises(ValidationError):
        CON29Field.model_validate_json(payload)


def test_manifest_round_trip_via_json_survives_even_though_the_python_constructor_would_reject_the_same_string():
    original = CON29Field(**_field(retrieved_at=_aware(2026, 8, 6, 12, 0, 0)))
    dumped = original.model_dump_json()
    restored = CON29Field.model_validate_json(dumped)
    assert restored == original


# --- answer: bool | str | None strict-mode union behaviour -------------

def test_answer_accepts_a_bool_true():
    field = CON29Field(**_field(answer=True))
    assert field.answer is True
    assert isinstance(field.answer, bool)


def test_answer_accepts_a_string():
    field = CON29Field(**_field(answer="yes"))
    assert field.answer == "yes"
    assert isinstance(field.answer, str)


def test_answer_accepts_none():
    field = CON29Field(**_field(answer=None))
    assert field.answer is None


def test_answer_rejects_int_one_rather_than_coercing_to_bool():
    with pytest.raises(ValidationError):
        CON29Field(**_field(answer=1))


def test_answer_rejects_int_zero_rather_than_coercing_to_bool_or_falsy_none():
    """
    Zero is the case most likely to slip through a bool/str union silently —
    a lax union might coerce 0 to False (bool) or to "" (str) without erroring.
    Strict mode must reject it outright, same as int 1.
    """
    with pytest.raises(ValidationError):
        CON29Field(**_field(answer=0))


def test_answer_string_true_is_not_coerced_to_bool():
    field = CON29Field(**_field(answer="true"))
    assert field.answer == "true"
    assert isinstance(field.answer, str)


# --- DEF-02: disposition/error consistency ------------------------------

def test_determinate_negative_with_an_error_is_rejected():
    with pytest.raises(ValidationError):
        CON29Field(**_field(disposition="determinate_negative", error="WFS call failed"))


def test_determinate_negative_without_an_error_is_valid():
    field = CON29Field(**_field(disposition="determinate_negative"))
    assert field.error is None


def test_unavailable_without_an_error_is_rejected():
    with pytest.raises(ValidationError):
        CON29Field(**_field(disposition="unavailable", error=None))


def test_unavailable_with_an_error_is_valid():
    field = CON29Field(**_field(disposition="unavailable", error="timed out"))
    assert field.disposition == "unavailable"


# --- cited_text mandatory for pdf_llm -----------------------------------

def test_pdf_llm_without_cited_text_is_rejected():
    with pytest.raises(ValidationError):
        CON29Field(**_field(retrieval_method="pdf_llm", cited_text=None))


def test_pdf_llm_with_cited_text_is_valid():
    field = CON29Field(**_field(retrieval_method="pdf_llm", cited_text="Permission is hereby granted"))
    assert field.cited_text is not None


def test_non_pdf_llm_without_cited_text_is_valid():
    field = CON29Field(**_field(retrieval_method="api", cited_text=None))
    assert field.cited_text is None


# --- required fields ------------------------------------------------------

def test_retrieval_method_is_required():
    with pytest.raises(ValidationError):
        CON29Field(
            question_id="3.5",
            question_text="Listed buildings.",
            disposition="flagged_manual",
        )


def test_none_is_a_valid_retrieval_method_for_flagged_manual():
    field = CON29Field(**_field(disposition="flagged_manual", retrieval_method="none"))
    assert field.retrieval_method == "none"


# --- PropertySearchResult -------------------------------------------------

def test_property_search_result_builds_with_a_list_of_fields():
    result = PropertySearchResult(
        search_id="7f82a91b",
        property_address="The Pineapple, 37 St Georges Road, Bristol BS1 5UU",
        uprn=_REALISTIC_UPRN,
        borough="bristol",
        search_timestamp=_aware(2026, 8, 6, 12, 0, 0),
        fields=[CON29Field(**_field())],
        coverage_summary={"determinate_positive": 1},
        overall_confidence="HIGH",
        conflicts_detected=0,
        eir_requests_generated=0,
    )
    assert result.system_notes == []
    assert result.model_dump(mode="json")["search_timestamp"] == "2026-08-06T12:00:00Z"


def test_property_search_result_system_notes_default_is_not_shared_between_instances():
    a = PropertySearchResult(
        search_id="a", property_address="x", uprn=None, borough="bristol",
        search_timestamp=_aware(2026, 8, 6, 12, 0, 0), fields=[],
        coverage_summary={}, overall_confidence="INDETERMINATE",
        conflicts_detected=0, eir_requests_generated=0,
    )
    a.system_notes.append("note")
    b = PropertySearchResult(
        search_id="b", property_address="y", uprn=None, borough="hackney",
        search_timestamp=_aware(2026, 8, 6, 12, 0, 0), fields=[],
        coverage_summary={}, overall_confidence="INDETERMINATE",
        conflicts_detected=0, eir_requests_generated=0,
    )
    assert b.system_notes == []
