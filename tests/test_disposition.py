"""
Tests for src/disposition.py (DEF-02).

The round-trip tests below are DEF-02's acceptance criterion made
executable: "a test asserting that a DatasetResult carrying an error never
produces determinate_negative." Each status is mapped to a disposition and
then actually used to construct a CON29Field, so the check exercises the
real invariant (CON29Field's own validator) rather than just asserting
against the mapping dict in isolation.
"""
import pytest
from pydantic import ValidationError

from src.disposition import disposition_for_dataset_status
from src.models import CON29Field


def _field(**overrides) -> dict:
    base = dict(question_id="3.5", question_text="Listed buildings.", retrieval_method="api")
    base.update(overrides)
    return base


def test_positive_maps_to_determinate_positive_and_builds_a_valid_field():
    disposition = disposition_for_dataset_status("positive")
    assert disposition == "determinate_positive"
    field = CON29Field(**_field(disposition=disposition))
    assert field.disposition == "determinate_positive"
    assert field.error is None


def test_negative_maps_to_determinate_negative_and_builds_a_valid_field():
    disposition = disposition_for_dataset_status("negative")
    assert disposition == "determinate_negative"
    field = CON29Field(**_field(disposition=disposition))
    assert field.disposition == "determinate_negative"
    assert field.error is None


def test_error_maps_to_unavailable_and_builds_a_valid_field_when_the_error_message_is_passed_through():
    disposition = disposition_for_dataset_status("error")
    assert disposition == "unavailable"
    field = CON29Field(**_field(disposition=disposition, error="WFS call failed: timeout"))
    assert field.disposition == "unavailable"
    assert field.error == "WFS call failed: timeout"


def test_error_status_never_produces_determinate_negative():
    """DEF-02's acceptance criterion, literally: a dataset that errored must
    never end up disposed as a confirmed negative answer."""
    assert disposition_for_dataset_status("error") != "determinate_negative"


def test_error_disposition_without_an_error_message_is_rejected_by_con29field():
    """
    The caller obligation documented in disposition_for_dataset_status's own
    docstring, made executable: this module returns "unavailable" for an
    "error" status but has no error message to attach. A caller that forgets
    to pass the real DatasetResult.error through must not be able to
    silently construct a valid-looking field anyway — CON29Field's own
    validator is the backstop.
    """
    disposition = disposition_for_dataset_status("error")
    with pytest.raises(ValidationError):
        CON29Field(**_field(disposition=disposition, error=None))


def test_error_status_cannot_be_forced_into_determinate_negative():
    """
    Covered from the other direction in test_models.py already, but DEF-02's
    acceptance criterion reads best assembled in one file here — and the
    original bug's real shape was exactly this: a call site setting both
    fields by hand (has_any() -> False, but the underlying DatasetResult
    carried a real error) rather than going through a mapping function at
    all.
    """
    with pytest.raises(ValidationError):
        CON29Field(**_field(disposition="determinate_negative", error="WFS call failed"))
