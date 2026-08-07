"""
Maps a dataset's raw query outcome onto the Section 5 four-state disposition
(src.models.Disposition) — DEF-02.

This is deliberately narrow: it is the minimum needed to make DEF-02's
acceptance criterion ("a DatasetResult carrying an error never produces
determinate_negative") checkable, not the full Sprint 3 CON29 Mapper
(WP-09), which will need registry/bucket context this module doesn't have.

DatasetStatus is a 3-state outcome — positive / negative / error — used
identically by PlanningDataResult.status_for and GisDataResult.status_for.
It deliberately does NOT distinguish gis_agent's `unavailable_reason`
("known gap, no attempt made") from a genuine `error` ("attempted and
failed"): both map to disposition `unavailable` here. Whether some
`unavailable_reason` stubs should instead map to `flagged_manual` ("no
permitted automated source exists") is a registry-reclassification
judgement call — DEF-10 / WP-05 territory — not decided by this module.

CALLER OBLIGATION this module does not enforce: CON29Field's own validator
(src/models.py) requires `error` to be set whenever `disposition` is
"unavailable", and requires it to be None whenever "determinate_negative".
`disposition_for_dataset_status("error")` returns "unavailable" but has no
access to the actual error message (this module only sees the 3-state
status, not the DatasetResult it came from) — the caller must pass the
real `.error` string through to `CON29Field(error=...)` itself, or
construction raises ValidationError. See
tests/test_disposition.py's round-trip tests, which construct a real
CON29Field for each status and are DEF-02's acceptance criterion made
executable rather than just described.
"""

from __future__ import annotations

from typing import Literal

from src.models import Disposition

DatasetStatus = Literal["positive", "negative", "error"]

_DISPOSITION_BY_STATUS: dict[DatasetStatus, Disposition] = {
    "positive": "determinate_positive",
    "negative": "determinate_negative",
    "error": "unavailable",
}


def disposition_for_dataset_status(status: DatasetStatus) -> Disposition:
    """
    See module docstring CALLER OBLIGATION: when status is "error", the
    caller must also pass the real error message through to
    CON29Field(error=...) itself — this function only returns the
    disposition, not the message, and CON29Field's own validator will
    raise ValidationError if error is left None on an "unavailable" field.
    """
    return _DISPOSITION_BY_STATUS[status]
