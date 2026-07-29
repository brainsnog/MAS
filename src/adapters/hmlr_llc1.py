"""
HMLR LLC1 adapter.

STATUS: BLOCKED as of 2026-07-22 — see CON29_ROADMAP_v2.md Current State /
Troubleshooting Log. There is no self-serve HMLR API key; LLC1 access is via
Business Gateway (Basic Auth: HMLR_BG_USERNAME / HMLR_BG_PASSWORD), which
requires an active Business e-services account not yet obtained.

Rather than leave a hole where this adapter should be, this module returns a
graceful-degradation stub for both boroughs (proposed 2026-07-25, confirmed
same session — see Architecture Decisions & Changes):

  - Bristol (LLC1-migrated, Gold status, July 2023): coverage_flag "manual"
    with a CREDENTIALS blocked_reason. TEMPORARY — once HMLR_BG_USERNAME /
    HMLR_BG_PASSWORD exist, swap `_fetch_bristol_stub` for a real Basic Auth
    call in that one function; nothing else in this file or in callers needs
    to change shape.
  - Hackney (not LLC1-migrated): coverage_flag "manual" with a different,
    STRUCTURAL blocked_reason. This stays manual even after Bristol's
    credentials blocker is resolved, per the Borough B design in
    CON29_ROADMAP_v2.md ("For Hackney (not migrated): marks all LLC1-sourced
    fields as coverage_flag: manual") — Hackney itself would need to migrate
    to HMLR's register for this to ever become an API source.

Covers CON29 questions 3.1 (land required for public purposes) and 3.12
(compulsory purchase) — see src/con29_registry.py.

NOTE for Sprint 3 (con29_mapper.py, not yet built): CON29Field, the final
strict-mode Pydantic output schema in CON29_ROADMAP_v2.md, has no dedicated
`blocked_reason` field. The mapper will need to fold `LLC1Result.blocked_reason`
into `CON29Field.answer_detail` (the only free-text field available) when it
maps this adapter's output. Recorded here so Sprint 3 doesn't have to
rediscover this.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional

Borough = Literal["bristol", "hackney"]

# CON29 questions this adapter is the primary_source for, per con29_registry.py.
COVERS_QUESTIONS: tuple[str, ...] = ("3.1", "3.12")

_BRISTOL_BLOCKED_REASON = (
    "HMLR Business Gateway Basic Auth required (HMLR_BG_USERNAME / "
    "HMLR_BG_PASSWORD env vars) — no self-serve API key exists. Blocked as "
    "of 2026-07-22; see CON29_ROADMAP_v2.md Current State / Troubleshooting "
    "Log. Bristol IS LLC1-migrated (July 2023, Gold status), so once "
    "credentials are obtained this becomes a real HIGH-confidence API "
    "source — this is a temporary, not structural, blocker."
)

_HACKNEY_BLOCKED_REASON = (
    "London Borough of Hackney has not migrated to HMLR's Local Land "
    "Charges register as of 2026 (see CON29_ROADMAP_v2.md Borough B / "
    "Group D). LLC1 charges must be obtained from the council's own "
    "register — HTML parsing (Bucket 2, if published) or an EIR Reg 5(1) "
    "request (Bucket 3). This is a STRUCTURAL manual field, not a "
    "credentials blocker: it stays manual even once HMLR_BG_USERNAME / "
    "HMLR_BG_PASSWORD exist, unless Hackney itself migrates to LLC1."
)


@dataclass(frozen=True)
class LLC1Charge:
    """One charge/entry from an LLC1 register. Real shape, once unblocked."""
    charge_type: str
    description: str
    instrument_reference: Optional[str] = None


@dataclass(frozen=True)
class LLC1Result:
    borough: Borough
    uprn: str
    coverage_flag: Literal["manual", "auto"]
    charges: list[LLC1Charge] = field(default_factory=list)
    source_name: str = "HM Land Registry — Local Land Charges (LLC1)"
    blocked_reason: Optional[str] = None
    retrieved_timestamp: Optional[str] = None
    covers_questions: tuple[str, ...] = COVERS_QUESTIONS


async def get_llc1_charges(uprn: str, borough: Borough) -> LLC1Result:
    """
    Fetch LLC1 charges for a property.

    Currently always returns a graceful-degradation stub — see module
    docstring. Never raises: a blocked/unavailable data source is a valid,
    expected outcome for this system's design (coverage_flag: "manual" +
    an EIR request template downstream), not a pipeline failure.

    Async even though the stub does no I/O yet, so the eventual real
    Basic Auth call is a drop-in replacement and this adapter can be
    dispatched the same way as the others in orchestrator.py's
    asyncio.gather (see CON29_ROADMAP_v2.md's pipeline pseudocode).
    """
    if borough == "bristol":
        return await _fetch_bristol_stub(uprn)
    return await _fetch_hackney_stub(uprn)


async def _fetch_bristol_stub(uprn: str) -> LLC1Result:
    """
    TEMPORARY stub. Replace with a real HMLR Business Gateway Basic Auth
    call once HMLR_BG_USERNAME / HMLR_BG_PASSWORD are available — see module
    docstring. Kept as its own function (rather than inlined in
    get_llc1_charges) specifically so that swap is a contained,
    single-function change later.
    """
    return LLC1Result(
        borough="bristol",
        uprn=uprn,
        coverage_flag="manual",
        charges=[],
        blocked_reason=_BRISTOL_BLOCKED_REASON,
        retrieved_timestamp=_now_iso(),
    )


async def _fetch_hackney_stub(uprn: str) -> LLC1Result:
    """
    Structural stub, not a temporary one — see module docstring. Expected to
    still return coverage_flag "manual" even after the Bristol path above is
    swapped for a real API call, unless Hackney migrates to LLC1.
    """
    return LLC1Result(
        borough="hackney",
        uprn=uprn,
        coverage_flag="manual",
        charges=[],
        blocked_reason=_HACKNEY_BLOCKED_REASON,
        retrieved_timestamp=_now_iso(),
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
