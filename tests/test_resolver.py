"""
Tests for src/resolver/property_resolver.py.

Uses httpx.MockTransport so these run with no network access and no API key —
suitable for CI and for running before real credentials exist. Fixtures are
REAL captured OS Places API responses (2026-07-25), not illustrative data —
see the `_fixture_note` field in each fixture file for capture details.
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


def _mock_transport(os_places_response: dict, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        if "api.os.uk" in str(request.url):
            return httpx.Response(status_code, json=os_places_response)
        if "planning.data.gov.uk" in str(request.url):
            # No local authority / boundary match in this simple test double —
            # resolver should degrade gracefully to None, not crash.
            return httpx.Response(200, json={"entities": []})
        raise AssertionError(f"Unexpected request to {request.url}")
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_resolve_bristol_address_returns_uprn_and_coords(monkeypatch):
    fixture = _load("bristol/os_places_find_example.json")
    transport = _mock_transport(fixture)

    def patched_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return _RealAsyncClient(*args, transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched_client)

    result = await pr.resolve("122 Whiteladies Road, Bristol BS8 2RP")

    assert result.uprn == "67678"
    assert result.postcode == "BS8 2RP"
    assert result.lat == pytest.approx(51.4686389)
    assert result.lon == pytest.approx(-2.6140011)
    assert result.match_score == pytest.approx(0.9)
    assert result.match_description == "GOOD"
    # Graceful degradation when planning.data.gov.uk has no match:
    assert result.local_authority_code is None
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
    transport = _mock_transport(fixture)

    def patched_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return _RealAsyncClient(*args, transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched_client)

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
    transport = _mock_transport(fixture)

    def patched_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return _RealAsyncClient(*args, transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched_client)

    result = await pr.resolve("14 Amhurst Road, London E8 1LL")

    assert result.match_score == pytest.approx(0.8)
    assert result.match_description == "GOOD"
    # The house number actually returned differs from what was asked for —
    # callers must compare result.address against the input themselves;
    # the resolver deliberately does not "fix" or hide this mismatch.
    assert "41" in result.address
    assert "14" not in result.address.split(",")[0]


@pytest.mark.asyncio
async def test_resolve_populates_local_authority_code_when_match_found(monkeypatch):
    """
    Confirms the documented planning.data.gov.uk query shape (entity.json?
    latitude=..&longitude=..&dataset=local-authority-district) as verified
    against https://www.planning.data.gov.uk/docs on 2026-07-25 — see
    Architecture Decisions & Changes.
    """
    fixture = _load("bristol/os_places_find_example.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if "api.os.uk" in str(request.url):
            return httpx.Response(200, json=fixture)
        if "planning.data.gov.uk" in str(request.url):
            assert "latitude" in str(request.url)
            assert "longitude" in str(request.url)
            return httpx.Response(200, json={
                "entities": [{"reference": "bristol", "name": "Bristol, City of"}]
            })
        raise AssertionError(f"Unexpected request to {request.url}")

    transport = httpx.MockTransport(handler)

    def patched_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return _RealAsyncClient(*args, transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched_client)

    result = await pr.resolve("1 Example Street, Bristol")

    assert result.local_authority_code == "bristol"


@pytest.mark.asyncio
async def test_resolve_not_found_raises_property_not_found_error(monkeypatch):
    transport = _mock_transport({"results": []})

    def patched_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return _RealAsyncClient(*args, transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched_client)

    with pytest.raises(pr.PropertyNotFoundError):
        await pr.resolve("Nonexistent Address, Nowhere")


@pytest.mark.asyncio
async def test_resolve_missing_api_key_raises_service_error(monkeypatch):
    monkeypatch.delenv("OS_PLACES_API_KEY", raising=False)
    with pytest.raises(pr.ResolverServiceError):
        await pr.resolve("1 Example Street, Bristol")
