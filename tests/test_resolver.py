"""
Tests for src/resolver/property_resolver.py.

Uses httpx.MockTransport so these run with no network access and no API key —
suitable for CI and for running before real credentials exist. Replace the
canned JSON with real captured fixtures once OS_PLACES_API_KEY is live in the
Codespace (Sprint 0 success criteria: capture 3-5 real fixture responses).
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

    result = await pr.resolve("1 Example Street, Bristol")

    assert result.uprn == "10009999999"
    assert result.postcode == "BS1 1AA"
    assert result.lat == pytest.approx(51.4536)
    assert result.lon == pytest.approx(-2.5975)
    # Graceful degradation when planning.data.gov.uk has no match:
    assert result.local_authority_code is None
    assert result.polygon_wkt is None


@pytest.mark.asyncio
async def test_resolve_hackney_address_returns_uprn_and_coords(monkeypatch):
    """
    Sprint 0 success criteria require the resolver to work for a Hackney
    address as well as a Bristol one (parity between the two borough case
    studies matters for every later sprint, not just this one).
    """
    fixture = _load("hackney/os_places_find_example.json")
    transport = _mock_transport(fixture)

    def patched_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return _RealAsyncClient(*args, transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched_client)

    result = await pr.resolve("14 Amhurst Road, Hackney, London E8 1LL")

    assert result.uprn == "100021234567"
    assert result.postcode == "E8 1LL"
    assert result.lat == pytest.approx(51.5462)
    assert result.lon == pytest.approx(-0.0615)


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
