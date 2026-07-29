"""
Tests for src/adapters/hmlr_llc1.py.

No mocking needed — the adapter is currently a pure stub (no network calls),
since real HMLR Business Gateway access is blocked. These tests exist to
lock in the stub's contract now, so swapping in a real Bristol API call
later is a change this test file will actually catch regressions on.
"""
import pytest

from src.adapters import hmlr_llc1
from src.con29_registry import get_registry


@pytest.mark.asyncio
async def test_bristol_returns_manual_with_credentials_blocked_reason():
    result = await hmlr_llc1.get_llc1_charges(uprn="67678", borough="bristol")

    assert result.borough == "bristol"
    assert result.uprn == "67678"
    assert result.coverage_flag == "manual"
    assert result.charges == []
    assert result.blocked_reason is not None
    assert "Business Gateway" in result.blocked_reason
    assert "HMLR_BG_USERNAME" in result.blocked_reason


@pytest.mark.asyncio
async def test_hackney_returns_manual_with_structural_blocked_reason():
    result = await hmlr_llc1.get_llc1_charges(uprn="10008231087", borough="hackney")

    assert result.borough == "hackney"
    assert result.coverage_flag == "manual"
    assert result.charges == []
    assert result.blocked_reason is not None
    assert "not migrated" in result.blocked_reason


@pytest.mark.asyncio
async def test_bristol_and_hackney_blocked_reasons_are_distinct():
    """
    The two boroughs are manual for different reasons (temporary credentials
    blocker vs. structural non-migration) — this distinction matters because
    only one of them should change once HMLR_BG credentials exist.
    """
    bristol = await hmlr_llc1.get_llc1_charges(uprn="67678", borough="bristol")
    hackney = await hmlr_llc1.get_llc1_charges(uprn="10008231087", borough="hackney")

    assert bristol.blocked_reason != hackney.blocked_reason


@pytest.mark.asyncio
async def test_never_raises():
    """A blocked source is an expected outcome, not a failure — must not raise."""
    await hmlr_llc1.get_llc1_charges(uprn="0", borough="bristol")
    await hmlr_llc1.get_llc1_charges(uprn="0", borough="hackney")


def test_covers_questions_matches_registry_primary_source():
    """
    Cross-check against con29_registry.py: every question this adapter claims
    to cover (COVERS_QUESTIONS) should actually list HMLR LLC1 as its
    primary_source in the registry, and vice versa. Catches drift between
    the two files if either changes independently.
    """
    registry_hmlr_ids = {
        q.question_id for q in get_registry() if "HMLR LLC1" in q.primary_source
    }
    assert set(hmlr_llc1.COVERS_QUESTIONS) == registry_hmlr_ids
