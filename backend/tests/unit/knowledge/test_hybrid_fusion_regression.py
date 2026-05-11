from __future__ import annotations

import pytest

from apps.knowledge.domain.index_build import IndexBuild
from apps.knowledge.domain.retrieval_profile import DEFAULT_RETRIEVAL_PROFILE
from apps.knowledge.service.runtime_store import SimpleRetrievalEngine


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _FakeVectorIndex:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def search_points(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(dict(kwargs))
        point_types = kwargs.get("point_types") or []
        payload_filter = kwargs.get("payload_filter") or {}
        if point_types == ["semantic_block"] and payload_filter:
            return []
        if point_types == ["semantic_block"]:
            return [{"id": "sb-1", "payload": {"point_type": "semantic_block", "text": "semantic block"}}]
        return []


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_block_first_retrieval_falls_back_from_filtered_semantic_to_unfiltered_semantic() -> None:
    vector = _FakeVectorIndex()
    engine = SimpleRetrievalEngine(lambda: vector)
    build = IndexBuild(
        tenant="demo",
        corpus_uuid="kb-1",
        index_profile_key="hybrid_v1",
        collection_name="kb_kb-1__hybrid_v1",
        metadata={},
    )

    hits = await engine.retrieve(
        query="Milyen allapotban van a London office?",
        builds=[build],
        retrieval_profile=DEFAULT_RETRIEVAL_PROFILE,
        query_profile={"time_filter": "current", "entity_type": "location"},
    )

    assert len(hits) == 1
    assert hits[0]["payload"]["point_type"] == "semantic_block"
    assert vector.calls[0]["point_types"] == ["semantic_block"]
    assert vector.calls[0]["payload_filter"] == {"time_modes": ["current"]}
    assert vector.calls[1]["point_types"] == ["semantic_block"]
    assert vector.calls[1].get("payload_filter") in (None, {})
    assert vector.calls[0]["lexical_query"] == "Milyen allapotban van a London office?"
