from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.knowledge.application.knowledge_service import KnowledgeBaseService
from apps.knowledge.domain.kb import KnowledgeBase

pytestmark = pytest.mark.unit


def _kb(idx: int) -> KnowledgeBase:
    return KnowledgeBase(
        id=idx,
        uuid=f"kb-{idx}",
        name=f"KB-{idx}",
        description="",
        qdrant_collection_name=f"collection-{idx}",
        created_at=None,
        updated_at=None,
    )


def test_build_context_for_chat_question_only_uses_allowed_kbs():
    repo = MagicMock()
    repo.list_all.return_value = [_kb(1), _kb(2)]
    repo.get_allowed_kb_ids_for_user.return_value = [2]
    repo.get_kb_ids_with_permission.return_value = [2]
    qdrant = MagicMock()

    async def _search_points(collection: str, query: str, limit: int, point_types, payload_filter):
        point_type = point_types[0]
        if collection != "collection-2":
            return []
        return [
            {
                "id": f"{point_type}-1",
                "score": 0.81,
                "payload": {
                    "text": f"{point_type} találat",
                    "source_point_id": "p-1",
                    "source_sentence_id": None,
                    "entity_ids": [11],
                    "predicate": "dolgozik",
                    "confidence": 0.7,
                    "strength": 0.6,
                    "place_keys": ["budapest"],
                },
            }
        ]

    qdrant.search_points = AsyncMock(side_effect=_search_points)
    svc = KnowledgeBaseService(repo=repo, qdrant_service=qdrant, user_repo=None, indexing_pipeline=None)

    packet = asyncio.run(
        svc.build_context_for_chat(
            question="Ki dolgozik Budapesten?",
            current_user_id=5,
            current_user_role="user",
            parsed_query={
                "intent": "activity",
                "entity_candidates": [],
                "time_candidates": [],
                "place_candidates": ["Budapest"],
                "predicate_candidates": ["dolgozik"],
            },
            kb_uuid=None,
            per_type_limit=5,
        )
    )

    assert packet["scoring_summary"]["kb_count"] == 1
    assert packet["scoring_summary"]["kb_uuids"] == ["kb-2"]
    assert len(packet["top_assertions"]) >= 1
    assert len(packet["evidence_sentences"]) >= 1
    assert len(packet["source_chunks"]) >= 1
    assert packet["scoring_summary"]["hybrid_recall_enabled"] is True
    assert packet["scoring_summary"]["query_embedding_reuse"] is True


def test_build_context_for_chat_denies_forbidden_kb_uuid():
    repo = MagicMock()
    repo.get_by_uuid.return_value = _kb(1)
    repo.get_kb_ids_with_permission.return_value = []
    qdrant = MagicMock()
    qdrant.search_points = AsyncMock(return_value=[])
    svc = KnowledgeBaseService(repo=repo, qdrant_service=qdrant, user_repo=None, indexing_pipeline=None)

    with pytest.raises(PermissionError):
        asyncio.run(
            svc.build_context_for_chat(
                question="Teszt",
                current_user_id=7,
                current_user_role="user",
                parsed_query={"intent": "summary", "entity_candidates": [], "time_candidates": [], "place_candidates": []},
                kb_uuid="kb-1",
            )
        )


def test_build_context_for_chat_resolves_places_and_uses_hybrid_queries():
    repo = MagicMock()
    repo.list_all.return_value = [_kb(2)]
    repo.get_allowed_kb_ids_for_user.return_value = [2]
    repo.get_kb_ids_with_permission.return_value = [2]
    repo.search_entity_candidates.return_value = []
    repo.get_assertion_neighbors.return_value = []
    repo.list_evidence_sentences.return_value = []
    repo.list_chunks_for_sentence_ids.return_value = []
    repo.get_entities_by_ids.return_value = []

    calls: list[dict] = []

    async def _search_points(collection: str, query: str, limit: int, point_types, payload_filter):
        calls.append(
            {
                "collection": collection,
                "query": query,
                "point_type": point_types[0],
                "payload_filter": payload_filter,
            }
        )
        ptype = point_types[0]
        if ptype == "assertion":
            return [
                {
                    "id": "assertion-1",
                    "score": 0.8,
                    "semantic_score": 0.8,
                    "lexical_score": 0.7,
                    "fusion_score": 0.78,
                    "payload": {
                        "text": "Anna dolgozik Budapesten",
                        "source_point_id": "p-1",
                        "entity_ids": [11],
                        "predicate": "dolgozik",
                        "place_keys": ["budapest"],
                        "confidence": 0.8,
                        "strength": 0.6,
                    },
                }
            ]
        if ptype == "sentence":
            return []
        if ptype == "structural_chunk":
            return []
        return []

    qdrant = MagicMock()
    qdrant.search_points = AsyncMock(side_effect=_search_points)
    svc = KnowledgeBaseService(repo=repo, qdrant_service=qdrant, user_repo=None, indexing_pipeline=None)
    packet = asyncio.run(
        svc.build_context_for_chat(
            question="Ki dolgozik Budapest területén?",
            current_user_id=5,
            current_user_role="user",
            parsed_query={
                "intent": "summary",
                "entity_candidates": [],
                "time_candidates": [],
                "place_candidates": ["Budapest"],
                "predicate_candidates": [],
                "query_embedding_text": "Budapest munka",
                "normalized_query_text": "budapest munka",
                "retrieval_mode": "assertion_first",
            },
            kb_uuid=None,
            per_type_limit=4,
        )
    )
    assert packet["scoring_summary"]["resolved_place_candidates"]["kb-2"] == ["budapest"]
    queried_texts = {c["query"] for c in calls}
    assert "Budapest munka" in queried_texts
    assert "budapest munka" in queried_texts
