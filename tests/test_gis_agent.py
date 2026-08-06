"""
Tests for src/agents/gis_agent.py.

Uses httpx.MockTransport — no network access needed. Bristol layer IDs used
in assertions below (1, 18) are the REAL ones captured 2026-08-02 via a real
Griff-run `?f=json` call — see gis_agent.py's module docstring. Hackney
typeNames used below (planning:tpo_point_as_area etc.) are likewise the real
values confirmed via a real WFS GetCapabilities call the same day. Response
payload *shapes* (attributes/properties keys) are illustrative, matching the
same "real endpoint, illustrative payload shape" split test_historic_england.py
already documents for its own query-response fixtures.
"""
import httpx
import pytest

from src.agents import gis_agent as ga

_RealAsyncClient = httpx.AsyncClient


def _patch_client(monkeypatch, handler):
    transport = httpx.MockTransport(handler)

    def patched_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return _RealAsyncClient(*args, transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched_client)


def _arcgis_feature_response(attributes_list: list[dict]) -> dict:
    return {"features": [{"attributes": a} for a in attributes_list]}


def _wfs_feature_response(properties_list: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": [{"properties": p} for p in properties_list]}


# ---------------------------------------------------------------------------
# Bristol (ArcGIS Server)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bristol_queries_correct_layer_ids_with_buffer_on_tpo_only(monkeypatch):
    queried = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        queried.append(url)
        return httpx.Response(200, json=_arcgis_feature_response([]))

    _patch_client(monkeypatch, handler)

    await ga.get_gis_data("bristol", lat=51.4686389, lon=-2.6140011)

    tpo_urls = [u for u in queried if "/18/query" in u]
    article4_urls = [u for u in queried if "/1/query" in u]
    assert len(tpo_urls) == 1
    assert len(article4_urls) == 1
    # TPO gets the 15m buffer, Article 4 does not (exact-intersects test).
    assert "distance=15" in tpo_urls[0]
    assert "distance" not in article4_urls[0]


@pytest.mark.asyncio
async def test_bristol_returns_matched_tpo_feature(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if "/18/query" in str(request.url):
            return httpx.Response(200, json=_arcgis_feature_response(
                [{"OBJECTID": 1, "TPO_REF": "TPO/2019/12"}]
            ))
        return httpx.Response(200, json=_arcgis_feature_response([]))

    _patch_client(monkeypatch, handler)

    result = await ga.get_gis_data("bristol", lat=51.0, lon=-2.0)

    assert result.has_any("tree_preservation_order") is True
    assert result.features_for("tree_preservation_order")[0]["TPO_REF"] == "TPO/2019/12"
    assert result.has_any("article_4_direction") is False


@pytest.mark.asyncio
async def test_bristol_one_dataset_failing_does_not_abort_the_other(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if "/1/query" in str(request.url):
            return httpx.Response(500, json={"error": "upstream problem"})
        return httpx.Response(200, json=_arcgis_feature_response([]))

    _patch_client(monkeypatch, handler)

    result = await ga.get_gis_data("bristol", lat=51.0, lon=-2.0)

    assert result.failed_datasets() == ["article_4_direction"]
    assert result.results["tree_preservation_order"].error is None


@pytest.mark.asyncio
async def test_bristol_rights_of_way_and_contaminated_land_are_unavailable_not_queried(monkeypatch):
    queried = []

    def handler(request: httpx.Request) -> httpx.Response:
        queried.append(str(request.url))
        return httpx.Response(200, json=_arcgis_feature_response([]))

    _patch_client(monkeypatch, handler)

    result = await ga.get_gis_data("bristol", lat=51.0, lon=-2.0)

    assert set(result.unavailable_datasets()) == {"rights_of_way", "contaminated_land"}
    assert result.results["rights_of_way"].unavailable_reason is not None
    assert result.results["contaminated_land"].unavailable_reason is not None
    # No network call made for either — only the two real Bristol layers hit.
    assert len(queried) == 2


# ---------------------------------------------------------------------------
# Hackney (GeoServer WFS)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hackney_queries_all_five_real_layers_with_buffer_on_tpo_only(monkeypatch):
    seen_type_names = []
    seen_filters = {}

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        type_name = params.get("typeName")
        seen_type_names.append(type_name)
        seen_filters[type_name] = params.get("CQL_FILTER")
        return httpx.Response(200, json=_wfs_feature_response([]))

    _patch_client(monkeypatch, handler)

    await ga.get_gis_data("hackney", lat=51.5462, lon=-0.0615)

    assert set(seen_type_names) == set(ga.HACKNEY_LAYERS.values())
    tpo_filter = seen_filters["planning:tpo_point_as_area"]
    assert "DWITHIN" in tpo_filter
    assert "15" in tpo_filter
    article4_filter = seen_filters["planning:article_4_direction"]
    assert "INTERSECTS" in article4_filter
    assert "DWITHIN" not in article4_filter


@pytest.mark.asyncio
async def test_hackney_srid_qualified_point_used_in_filter(monkeypatch):
    """CQL geometry must be SRID-qualified so GeoServer can reproject the
    WGS84 point against layers stored natively in EPSG:27700 — see module
    docstring REMAINING, LOWER-RISK GAP."""
    captured_filter = {}

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        if params.get("typeName") == "planning:conservation_area":
            captured_filter["value"] = params.get("CQL_FILTER")
        return httpx.Response(200, json=_wfs_feature_response([]))

    _patch_client(monkeypatch, handler)

    await ga.get_gis_data("hackney", lat=51.5462, lon=-0.0615)

    assert "SRID=4326" in captured_filter["value"]
    assert "POINT(-0.0615 51.5462)" in captured_filter["value"]


@pytest.mark.asyncio
async def test_hackney_returns_matched_contaminated_land_feature(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        if params.get("typeName") == "pollution:part2a_site_investigated":
            return httpx.Response(200, json=_wfs_feature_response(
                [{"site_name": "Former gasworks site", "status": "investigated"}]
            ))
        return httpx.Response(200, json=_wfs_feature_response([]))

    _patch_client(monkeypatch, handler)

    result = await ga.get_gis_data("hackney", lat=51.5462, lon=-0.0615)

    assert result.has_any("contaminated_land_part2a_investigated") is True
    assert (
        result.features_for("contaminated_land_part2a_investigated")[0]["site_name"]
        == "Former gasworks site"
    )
    assert result.has_any("contaminated_land_part2a_concern") is False


@pytest.mark.asyncio
async def test_hackney_one_dataset_failing_does_not_abort_the_others(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        if params.get("typeName") == "planning:brownfield_register":
            return httpx.Response(500, json={"error": "upstream problem"})
        return httpx.Response(200, json=_wfs_feature_response([]))

    _patch_client(monkeypatch, handler)

    result = await ga.get_gis_data("hackney", lat=51.5462, lon=-0.0615)

    assert result.failed_datasets() == ["brownfield_register"]
    other_datasets = {
        "tree_preservation_order", "article_4_direction",
        "conservation_area", "contaminated_land_part2a_investigated",
        "contaminated_land_part2a_concern",
    }
    for dataset in other_datasets:
        assert result.results[dataset].error is None


@pytest.mark.asyncio
async def test_hackney_rights_of_way_is_unavailable_not_queried(monkeypatch):
    queried = []

    def handler(request: httpx.Request) -> httpx.Response:
        queried.append(dict(request.url.params).get("typeName"))
        return httpx.Response(200, json=_wfs_feature_response([]))

    _patch_client(monkeypatch, handler)

    result = await ga.get_gis_data("hackney", lat=51.5462, lon=-0.0615)

    assert result.unavailable_datasets() == ["rights_of_way"]
    assert result.results["rights_of_way"].unavailable_reason is not None
    # Only the 6 real Hackney layers hit, nothing resembling rights-of-way.
    assert len(queried) == 6
    assert all(t is not None for t in queried)


# ---------------------------------------------------------------------------
# Cross-cutting
# ---------------------------------------------------------------------------

def test_tpo_buffer_is_15m_confirmed_with_griff_2026_08_02():
    assert ga.TPO_BUFFER_M == 15


def test_dataset_to_questions_covers_the_documented_question_set():
    """Same looser check as planning_agent.py's equivalent test — this
    agent's coverage is opportunistic/borough-specific (see module
    docstring), not a strict registry primary_source match."""
    documented = {"3.9m", "1.2", "3.11", "3.13", "2.2", "2.3", "2.4", "2.5"}
    covered = {q for questions in ga.DATASET_TO_QUESTIONS.values() for q in questions}
    assert covered == documented
    assert "3.7" not in covered
    assert "1.1h" not in covered


def test_article_4_is_queried_but_not_mapped_to_a_con29_question():
    """Article 4 directions have no standalone CON29 Part 1 question number
    in the real form (con29_registry.py, rebuilt 2026-08-02) — must still be
    queried by both boroughs' backends (real, useful data) but must NOT
    appear in DATASET_TO_QUESTIONS."""
    assert "article_4_direction" not in ga.DATASET_TO_QUESTIONS
    assert "article_4_direction" in ga.NON_CON29_DATASETS
    # Still genuinely queried — confirmed via the layer/typeName tables,
    # not just the question-mapping dict.
    assert "article_4_direction" in ga.BRISTOL_LAYER_IDS
    assert "article_4_direction" in ga.HACKNEY_LAYERS


def test_bristol_layer_ids_are_not_reused_from_a_different_councils_service():
    """
    Regression test for the near-miss noted in the module docstring: a
    generic web search for an "INSPIRE MapServer" surfaces City of London's
    identically-named but differently-numbered service. Bristol's own
    confirmed layers (id 1 = Article 4 Directions, id 18 = TPO trunk) must
    not silently drift to match some other council's numbering.
    """
    assert ga.BRISTOL_LAYER_IDS["article_4_direction"] == 1
    assert ga.BRISTOL_LAYER_IDS["tree_preservation_order"] == 18
