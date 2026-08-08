"""
Tests for src/adapters/historic_england.py.

Uses httpx.MockTransport — no network access, no key needed (matches the
adapter's own expectation that none is required).

FEATURE_SERVER_ROOT_RESPONSE below is the REAL layer list, captured 2026-07-25
via a real `?f=json` call (see historic_england.py's module docstring) — not
illustrative data, unlike the query-response fixtures below it, which remain
illustrative since the exact attribute-key casing on a real `/query` call is
still an open (lower-risk) item.
"""
import httpx
import pytest

from src.adapters import historic_england as he

_RealAsyncClient = httpx.AsyncClient

# REAL layer list, captured 2026-07-25 (see historic_england.py docstring).
# Deliberately includes id 6-10 (Scheduled Monuments, Parks and Gardens,
# Battlefields, Protected Wreck Sites, World Heritage Sites) even though this
# adapter doesn't use them, so the "listed building" match logic is tested
# against the real, full candidate pool, not a trimmed-down convenience list.
FEATURE_SERVER_ROOT_RESPONSE = {
    "layers": [
        {"id": 0, "name": "Listed Building points"},
        {"id": 1, "name": "Building Preservation Notice points"},
        {"id": 2, "name": "Certificate of Immunity points"},
        {"id": 3, "name": "Listed Building polygons"},
        {"id": 4, "name": "Building Preservation Notices polygons"},
        {"id": 5, "name": "Certificate of Immunity polygons"},
        {"id": 6, "name": "Scheduled Monuments"},
        {"id": 7, "name": "Parks and Gardens"},
        {"id": 8, "name": "Battlefields"},
        {"id": 9, "name": "Protected Wreck Sites"},
        {"id": 10, "name": "World Heritage Sites"},
    ]
}

QUERY_RESPONSE_MATCH = {
    "features": [
        {
            "attributes": {
                "OBJECTID": 12345,
                "ListEntry": "1234567",
                "Name": "122-124, WHITELADIES ROAD",
                "Grade": "II",
                "ListDate": "1977-03-04",
            }
        }
    ]
}

QUERY_RESPONSE_NO_MATCH = {"features": []}


def _mock_transport(query_response: dict, root_response: dict = FEATURE_SERVER_ROOT_RESPONSE):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/query" in url:
            return httpx.Response(200, json=query_response)
        return httpx.Response(200, json=root_response)
    return httpx.MockTransport(handler)


def _patch_client(monkeypatch, transport):
    def patched_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return _RealAsyncClient(*args, transport=transport, **kwargs)
    monkeypatch.setattr(httpx, "AsyncClient", patched_client)


@pytest.fixture(autouse=True)
def reset_layer_id_cache():
    """The adapter caches the discovered layer id at module level — reset
    between tests so one test's discovery doesn't leak into another."""
    he._listed_building_layer_id = None
    yield
    he._listed_building_layer_id = None


@pytest.mark.asyncio
async def test_prefers_points_layer_over_polygon_layer(monkeypatch):
    """
    The actual fix: this service has BOTH "Listed Building points" (id 0)
    and "Listed Building polygons" (id 3) — confirmed 2026-07-25. The
    points layer must be chosen, since HE's own docs say the polygon layer
    only covers buildings listed/amended since April 2011 and is therefore
    NOT the comprehensive one.
    """
    queried_urls = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        queried_urls.append(url)
        if "/query" in url:
            return httpx.Response(200, json=QUERY_RESPONSE_NO_MATCH)
        return httpx.Response(200, json=FEATURE_SERVER_ROOT_RESPONSE)

    transport = httpx.MockTransport(handler)
    _patch_client(monkeypatch, transport)

    await he.get_listed_building_status(lat=51.4686389, lon=-2.6140011)

    query_urls = [u for u in queried_urls if "/query" in u]
    assert len(query_urls) == 1
    assert "/0/query" in query_urls[0]
    assert "/3/query" not in query_urls[0]


@pytest.mark.asyncio
async def test_prefers_points_layer_even_when_polygon_listed_first(monkeypatch):
    """
    Same assertion as above, but with the polygon layer deliberately placed
    BEFORE the points layer in the array. This is the real regression test
    for the fix — the original version of this function effectively relied
    on points happening to come first; this proves the current version
    chooses correctly on purpose, not by list-order luck.
    """
    reordered_root_response = {
        "layers": [
            {"id": 3, "name": "Listed Building polygons"},
            {"id": 0, "name": "Listed Building points"},
        ]
    }
    queried_urls = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        queried_urls.append(url)
        if "/query" in url:
            return httpx.Response(200, json=QUERY_RESPONSE_NO_MATCH)
        return httpx.Response(200, json=reordered_root_response)

    transport = httpx.MockTransport(handler)
    _patch_client(monkeypatch, transport)

    await he.get_listed_building_status(lat=51.0, lon=-2.0)

    query_urls = [u for u in queried_urls if "/query" in u]
    assert "/0/query" in query_urls[0]
    assert "/3/query" not in query_urls[0]


@pytest.mark.asyncio
async def test_returns_listed_building_true_with_grade_and_entry(monkeypatch):
    transport = _mock_transport(QUERY_RESPONSE_MATCH)
    _patch_client(monkeypatch, transport)

    result = await he.get_listed_building_status(lat=51.4686389, lon=-2.6140011)

    assert result.listed_building is True
    assert result.grade == "II"
    assert result.list_entry == "1234567"
    assert result.match_count == 1
    # DEF-04: retrieved_at must be timezone-aware — the dataclass can't
    # enforce this the way CON29Field's AwareDatetime does, so this catches
    # a bare datetime.now() rather than datetime.now(timezone.utc).
    assert result.retrieved_at.tzinfo is not None
    assert result.source_url is not None


@pytest.mark.asyncio
async def test_returns_listed_building_false_when_no_match(monkeypatch):
    transport = _mock_transport(QUERY_RESPONSE_NO_MATCH)
    _patch_client(monkeypatch, transport)

    result = await he.get_listed_building_status(lat=0.0, lon=0.0)

    assert result.listed_building is False
    assert result.grade is None
    assert result.list_entry is None
    assert result.match_count == 0


@pytest.mark.asyncio
async def test_layer_discovery_is_cached_across_calls(monkeypatch):
    """Confirms the layer id is only discovered once per process, not on
    every single call — the adapter should not re-fetch ?f=json each time."""
    call_count = {"root": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/query" in url:
            return httpx.Response(200, json=QUERY_RESPONSE_NO_MATCH)
        call_count["root"] += 1
        return httpx.Response(200, json=FEATURE_SERVER_ROOT_RESPONSE)

    transport = httpx.MockTransport(handler)
    _patch_client(monkeypatch, transport)

    await he.get_listed_building_status(lat=51.0, lon=-2.0)
    await he.get_listed_building_status(lat=52.0, lon=-1.0)

    assert call_count["root"] == 1


@pytest.mark.asyncio
async def test_returns_unavailable_error_if_no_listed_building_layer_found(monkeypatch):
    """
    REWRITTEN 2026-08-06 (DEF-09): this used to assert a raised
    HistoricEnglandServiceError. The adapter no longer raises at all — it's
    the only one of the four adapters/agents that did, and DEF-09's fix is
    "adapters never raise, they return a result carrying error" applied
    consistently. Same failure condition, a different, now-consistent
    shape: an error-carrying result, listed_building=None (not False, so
    the error can never be mistaken for a confirmed negative — DEF-02's
    discipline applies here too).
    """
    root_with_no_match = {"layers": [{"id": 0, "name": "Conservation Areas"}]}
    transport = _mock_transport(QUERY_RESPONSE_NO_MATCH, root_response=root_with_no_match)
    _patch_client(monkeypatch, transport)

    result = await he.get_listed_building_status(lat=51.0, lon=-2.0)

    assert result.listed_building is None
    assert result.error is not None
    assert "no layer matching" in result.error.lower()
    assert result.retrieved_at.tzinfo is not None


@pytest.mark.asyncio
async def test_returns_unavailable_error_on_a_genuine_query_failure(monkeypatch):
    """The other never-raise path: discovery succeeds, but the /query call
    itself fails (bad response shape here, standing in for a real HTTP
    failure — httpx.MockTransport can't easily simulate a connection
    error, but the except clause treats ValueError the same as
    httpx.RequestError/HTTPStatusError)."""
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/query" in url:
            return httpx.Response(200, content=b"not valid json")
        return httpx.Response(200, json=FEATURE_SERVER_ROOT_RESPONSE)

    transport = httpx.MockTransport(handler)
    _patch_client(monkeypatch, transport)

    result = await he.get_listed_building_status(lat=51.0, lon=-2.0)

    assert result.listed_building is None
    assert result.error is not None
    assert "NHLE query failed" in result.error
    assert result.retrieved_at.tzinfo is not None


def test_covers_questions_matches_registry_primary_source():
    from src.con29_registry import get_registry

    registry_he_ids = {
        q.question_id for q in get_registry() if "Historic England" in q.primary_source
    }
    assert set(he.COVERS_QUESTIONS) == registry_he_ids
