"""
Tests for src/agents/planning_agent.py.

Uses httpx.MockTransport — no network access needed, planning.data.gov.uk
requires no key. Fixture entity shapes are illustrative (reference, name,
entry-date — the commonly-seen planning.data.gov.uk entity fields) rather
than live-captured, since this agent hasn't had a real call yet either.
"""
import httpx
import pytest

from src.agents import planning_agent as pa

_RealAsyncClient = httpx.AsyncClient


def _entity_response(entities: list[dict]) -> dict:
    return {"entities": entities}


def _patch_client(monkeypatch, handler):
    transport = httpx.MockTransport(handler)

    def patched_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return _RealAsyncClient(*args, transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched_client)


@pytest.mark.asyncio
async def test_queries_every_dataset_and_groups_results(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        dataset = dict(request.url.params).get("dataset")
        if dataset == "planning-application":
            return httpx.Response(200, json=_entity_response([
                {"reference": "2024/0123/FUL", "name": "Extension to rear"},
                {"reference": "2023/9988/FUL", "name": "Loft conversion"},
            ]))
        if dataset == "conservation-area":
            return httpx.Response(200, json=_entity_response([
                {"reference": "CA-12", "name": "Clifton Conservation Area"},
            ]))
        # Every other dataset: no match, valid empty response.
        return httpx.Response(200, json=_entity_response([]))

    _patch_client(monkeypatch, handler)

    result = await pa.get_planning_data(lat=51.4686389, lon=-2.6140011)

    assert set(result.results.keys()) == set(pa.DATASET_TO_QUESTIONS.keys())
    assert len(result.entities_for("planning-application")) == 2
    assert result.has_any("planning-application") is True
    assert result.entities_for("conservation-area")[0]["name"] == "Clifton Conservation Area"
    assert result.has_any("tree-preservation-order") is False
    assert result.failed_datasets() == []


@pytest.mark.asyncio
async def test_one_dataset_failing_does_not_abort_the_others(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        dataset = dict(request.url.params).get("dataset")
        if dataset == "tree-preservation-order":
            return httpx.Response(500, json={"error": "upstream problem"})
        return httpx.Response(200, json=_entity_response([]))

    _patch_client(monkeypatch, handler)

    result = await pa.get_planning_data(lat=51.0, lon=-2.0)

    assert result.failed_datasets() == ["tree-preservation-order"]
    assert result.results["tree-preservation-order"].error is not None
    # Every other dataset still queried successfully despite the one failure:
    other_datasets = set(pa.DATASET_TO_QUESTIONS) - {"tree-preservation-order"}
    for dataset in other_datasets:
        assert result.results[dataset].error is None


@pytest.mark.asyncio
async def test_all_datasets_queried_with_correct_point_params(monkeypatch):
    seen_datasets = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        seen_datasets.append(params.get("dataset"))
        assert params.get("latitude") == "51.5"
        assert params.get("longitude") == "-0.1"
        return httpx.Response(200, json=_entity_response([]))

    _patch_client(monkeypatch, handler)

    await pa.get_planning_data(lat=51.5, lon=-0.1)

    assert set(seen_datasets) == set(pa.DATASET_TO_QUESTIONS.keys())


def test_dataset_to_questions_covers_the_documented_sprint1_questions():
    """
    Not a strict registry cross-check like the HMLR/Historic England
    adapters — this agent deliberately covers 1.1h opportunistically even
    though the registry's declared primary_source for it is the council
    website (Bucket 2), per the module docstring. So this test only checks
    the documented Sprint 1 §C question set is present, not an exact-match
    against registry primary_source strings.
    """
    documented = {
        "1.1a", "1.1b", "1.1c", "1.1d", "1.1e", "1.1f", "1.1g",
        "1.2", "3.11", "1.1h", "3.7", "3.5", "3.13",
    }
    covered = {q for questions in pa.DATASET_TO_QUESTIONS.values() for q in questions}
    assert covered == documented
