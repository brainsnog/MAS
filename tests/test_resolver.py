"""
Tests for src/resolver/property_resolver.py.

Uses httpx.MockTransport so these run with no network access and no API key —
suitable for CI and for running before real credentials exist. Fixtures are
REAL captured OS Places API responses (2026-07-25), not illustrative data —
see the `_fixture_note` field in each fixture file for capture details.

DEF-03, 2026-08-06: test_resolve_populates_local_authority_code_when_match_found
used to mock planning.data.gov.uk's local-authority-district response with a
fabricated `"reference": "bristol"` value — never confirmed against a real
response, an invented string chosen to make the old (str) local_authority_code
field read nicely. Deleted rather than kept and patched: a test asserting an
invented value is worse than no test. Replaced with tests built on
organisation-entity 66/163, values this project has actually seen returned by
planning.data.gov.uk (on the brownfield-land dataset — see property_resolver.py's
module docstring for what is and isn't yet confirmed about this).
"""
import json
from pathlib import Path

import httpx
import pytest

from src.resolver import property_resolver as pr

FIXTURES = Path(__file__).parent / "fixtures"
_RealAsyncClient = httpx.AsyncClient


def _load(path: str) -> dict:
    with open(FIXTURES / path) as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    monkeypatch.setenv("OS_PLACES_API_KEY", "test-key-not-real")


def _mock_transport(os_places_response: dict, status_code: int = 200,
                     local_authority_entities: list[dict] | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if "api.os.uk" in str(request.url):
            return httpx.Response(status_code, json=os_places_response)
        if "planning.data.gov.uk" in str(request.url):
            # No local authority / boundary match in this simple test double —
            # resolver should degrade gracefully to None, not crash.
            return httpx.Response(200, json={"entities": local_authority_entities or []})
        raise AssertionError(f"Unexpected request to {request.url}")
    return httpx.MockTransport(handler)


def _patch_client(monkeypatch, transport):
    def patched_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return _RealAsyncClient(*args, transport=transport, **kwargs)
    monkeypatch.setattr(httpx, "AsyncClient", patched_client)


@pytest.mark.asyncio
async def test_resolve_bristol_address_returns_uprn_and_coords(monkeypatch):
    fixture = _load("bristol/os_places_find_example.json")
    _patch_client(monkeypatch, _mock_transport(fixture))

    result = await pr.resolve("122 Whiteladies Road, Bristol BS8 2RP")

    assert result.uprn == "67678"
    assert result.postcode == "BS8 2RP"
    assert result.lat == pytest.approx(51.4686389)
    assert result.lon == pytest.approx(-2.6140011)
    assert result.match_score == pytest.approx(0.9)
    assert result.match_description == "GOOD"
    # Graceful degradation when planning.data.gov.uk has no match:
    assert result.local_authority_code is None
    assert result.borough is None
    assert result.polygon_wkt is None


@pytest.mark.asyncio
async def test_resolve_hackney_address_returns_uprn_and_coords(monkeypatch):
    """
    Sprint 0 success criteria require the resolver to work for a Hackney
    address as well as a Bristol one (parity between the two borough case
    studies matters for every later sprint, not just this one).

    NOTE: this fixture is a real captured response for "14 Amhurst Road,
    London E8 1LL" — the fictional example address from CON29_ROADMAP_v2.md's
    own Evidence Manifest Schema. Number 14 doesn't exist on this street; OS
    Places API returned number 41 as its best real candidate, still labelled
    MATCH_DESCRIPTION: "GOOD". This is exactly the scenario match_score exists
    to surface — see test_resolve_surfaces_match_confidence_for_caller below.
    """
    fixture = _load("hackney/os_places_find_example.json")
    _patch_client(monkeypatch, _mock_transport(fixture))

    result = await pr.resolve("14 Amhurst Road, London E8 1LL")

    assert result.uprn == "10008231087"
    assert result.postcode == "E8 1LL"
    assert result.lat == pytest.approx(51.547983)
    assert result.lon == pytest.approx(-0.0574934)


@pytest.mark.asyncio
async def test_resolve_surfaces_match_confidence_for_caller(monkeypatch):
    """
    The Hackney fixture is a "GOOD"/0.8-scored match on a DIFFERENT house
    number than what was asked for (41 returned for a search on 14, which
    doesn't exist). resolve() must not hide this — it's the caller's job to
    decide what to do with a less-than-exact match, but only if the signal
    is actually surfaced. This test exists to make sure that stays true even
    if the DPA parsing logic changes later.
    """
    fixture = _load("hackney/os_places_find_example.json")
    _patch_client(monkeypatch, _mock_transport(fixture))

    result = await pr.resolve("14 Amhurst Road, London E8 1LL")

    assert result.match_score == pytest.approx(0.8)
    assert result.match_description == "GOOD"
    # The house number actually returned differs from what was asked for —
    # callers must compare result.address against the input themselves;
    # the resolver deliberately does not "fix" or hide this mismatch.
    assert "41" in result.address
    assert "14" not in result.address.split(",")[0]


@pytest.mark.asyncio
async def test_resolve_populates_address_components_from_dpa(monkeypatch):
    """DEF-03: BUILDING_NUMBER/THOROUGHFARE_NAME/POST_TOWN etc. from the DPA
    response, previously discarded in favour of only the concatenated
    ADDRESS string. Bristol's real fixture has no SUB_BUILDING_NAME/
    BUILDING_NAME (a plain numbered shop front), so those two stay None —
    itself a real, useful negative case, not a gap in the test."""
    fixture = _load("bristol/os_places_find_example.json")
    _patch_client(monkeypatch, _mock_transport(fixture))

    result = await pr.resolve("122 Whiteladies Road, Bristol BS8 2RP")

    assert result.building_number == "122"
    assert result.thoroughfare_name == "WHITELADIES ROAD"
    assert result.post_town == "BRISTOL"
    assert result.sub_building_name is None
    assert result.building_name is None


@pytest.mark.asyncio
async def test_resolve_generates_a_search_id_when_none_supplied(monkeypatch):
    fixture = _load("bristol/os_places_find_example.json")
    _patch_client(monkeypatch, _mock_transport(fixture))

    result = await pr.resolve("122 Whiteladies Road, Bristol BS8 2RP")

    assert result.search_id  # non-empty
    assert isinstance(result.search_id, str)


@pytest.mark.asyncio
async def test_resolve_uses_the_supplied_search_id_when_given(monkeypatch):
    fixture = _load("bristol/os_places_find_example.json")
    _patch_client(monkeypatch, _mock_transport(fixture))

    result = await pr.resolve("122 Whiteladies Road, Bristol BS8 2RP", search_id="abc-123")

    assert result.search_id == "abc-123"


@pytest.mark.asyncio
async def test_resolve_captures_retrieved_at_as_an_aware_datetime(monkeypatch):
    fixture = _load("bristol/os_places_find_example.json")
    _patch_client(monkeypatch, _mock_transport(fixture))

    result = await pr.resolve("122 Whiteladies Road, Bristol BS8 2RP")

    # DEF-04: the dataclass can't enforce timezone-awareness the way
    # CON29Field's AwareDatetime does — this catches a bare datetime.now().
    assert result.retrieved_at.tzinfo is not None


@pytest.mark.asyncio
async def test_resolve_captures_a_redacted_source_url_never_the_raw_api_key(monkeypatch):
    """DEF-04 security constraint, literally: the OS Places URL carries the
    key as a query parameter, and it must never reach ResolvedProperty
    unredacted."""
    fixture = _load("bristol/os_places_find_example.json")
    _patch_client(monkeypatch, _mock_transport(fixture))

    result = await pr.resolve("122 Whiteladies Road, Bristol BS8 2RP")

    assert result.source_url is not None
    assert "test-key-not-real" not in result.source_url
    assert "key=REDACTED" in result.source_url
    assert "api.os.uk" in result.source_url


@pytest.mark.asyncio
async def test_resolve_populates_borough_when_organisation_entity_is_bristol(monkeypatch):
    """
    DEF-03: local_authority_code now holds planning.data.gov.uk's
    organisation-entity value, not the previous version's fabricated
    "reference" string. 66 is Bristol City Council's real organisation-entity,
    confirmed live in Handoff Section 3.5 — not an invented value.
    """
    fixture = _load("bristol/os_places_find_example.json")
    transport = _mock_transport(
        fixture, local_authority_entities=[{"organisation-entity": 66}]
    )
    _patch_client(monkeypatch, transport)

    result = await pr.resolve("122 Whiteladies Road, Bristol BS8 2RP")

    assert result.local_authority_code == 66
    assert result.borough == "bristol"


@pytest.mark.asyncio
async def test_resolve_populates_borough_when_organisation_entity_is_hackney(monkeypatch):
    fixture = _load("hackney/os_places_find_example.json")
    transport = _mock_transport(
        fixture, local_authority_entities=[{"organisation-entity": 163}]
    )
    _patch_client(monkeypatch, transport)

    result = await pr.resolve("14 Amhurst Road, London E8 1LL")

    assert result.local_authority_code == 163
    assert result.borough == "hackney"


@pytest.mark.asyncio
async def test_resolve_raises_property_out_of_scope_for_a_confirmed_other_authority(monkeypatch):
    """
    DEF-03's rejection path. 999 is an arbitrary, clearly-not-66-or-163
    illustrative value for this unit test (standing in for e.g. Manchester)
    — not a claimed real organisation-entity for any specific council, same
    test-double discipline as test_resolve_not_found_raises_property_not_found_error's
    empty results list. The point under test is the rejection behaviour for
    ANY confirmed non-Bristol/non-Hackney value, not a specific council's id.
    """
    fixture = _load("bristol/os_places_find_example.json")
    transport = _mock_transport(
        fixture, local_authority_entities=[{"organisation-entity": 999}]
    )
    _patch_client(monkeypatch, transport)

    with pytest.raises(pr.PropertyOutOfScopeError):
        await pr.resolve("Somewhere else entirely")


@pytest.mark.asyncio
async def test_resolve_does_not_raise_when_local_authority_is_merely_undetermined(monkeypatch):
    """
    Contrast with the out-of-scope test above: an absent/undetermined
    local authority (the default empty-entities mock) must NOT raise —
    only a confirmed wrong answer does. This is resolve()'s existing
    "never raises on missing local_authority_code" behaviour, preserved.
    """
    fixture = _load("bristol/os_places_find_example.json")
    _patch_client(monkeypatch, _mock_transport(fixture))

    result = await pr.resolve("122 Whiteladies Road, Bristol BS8 2RP")

    assert result.local_authority_code is None
    assert result.borough is None


@pytest.mark.asyncio
async def test_resolve_not_found_raises_property_not_found_error(monkeypatch):
    transport = _mock_transport({"results": []})
    _patch_client(monkeypatch, transport)

    with pytest.raises(pr.PropertyNotFoundError):
        await pr.resolve("Nonexistent Address, Nowhere")


@pytest.mark.asyncio
async def test_resolve_missing_api_key_raises_service_error(monkeypatch):
    monkeypatch.delenv("OS_PLACES_API_KEY", raising=False)
    with pytest.raises(pr.ResolverServiceError):
        await pr.resolve("1 Example Street, Bristol")
