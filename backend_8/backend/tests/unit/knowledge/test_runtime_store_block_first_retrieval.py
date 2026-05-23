import asyncio

from apps.knowledge.domain.index_build import IndexBuild
from apps.knowledge.domain.retrieval_profile import DEFAULT_RETRIEVAL_PROFILE
from apps.knowledge.service.runtime_store import SimpleRetrievalEngine


class _FakeVectorIndex:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def search_points(self, **kwargs):
        self.calls.append(dict(kwargs))
        point_types = kwargs.get("point_types")
        if point_types == ["semantic_block"]:
            return [
                {
                    "id": "qdrant-block-1",
                    "score": 0.91,
                    "fusion_score": 0.95,
                    "payload": {
                        "point_type": "semantic_block",
                        "block_id": "block-1",
                        "retrieval_weight": 0.8,
                        "text": "Alany: SK MAX rendszer\nAz SK MAX rendszer kezeli a szerződéseket.",
                    },
                }
            ]
        return []


def test_retrieval_engine_searches_semantic_blocks_first() -> None:
    fake_index = _FakeVectorIndex()
    engine = SimpleRetrievalEngine(lambda: fake_index)
    build = IndexBuild(
        tenant="tenant",
        corpus_uuid="kb-1",
        index_profile_key="hybrid_v1",
        collection_name="kb_collection__hybrid_v1",
    )

    hits = asyncio.run(
        engine.retrieve(
            query="Mit csinál az SK MAX rendszer?",
            builds=[build],
            retrieval_profile=DEFAULT_RETRIEVAL_PROFILE,
            query_profile={},
        )
    )

    assert hits[0]["payload"]["point_type"] == "semantic_block"
    assert hits[0]["payload"]["block_id"] == "block-1"
    assert hits[0]["fusion_score"] == 0.76
    assert hits[0]["payload"]["quality_score_explanation"]["retrieval_weight"] == 0.8
    assert fake_index.calls[0]["point_types"] == ["semantic_block"]
