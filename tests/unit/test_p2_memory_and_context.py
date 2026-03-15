from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.knowledge.application.context_builder import KnowledgeContextBuilder
from apps.knowledge.application.indexing_pipeline import KnowledgeIndexingPipeline
from apps.knowledge.application.query_parser import QueryParser
from apps.knowledge.application.reranker import compute_final_score
from apps.knowledge.application.knowledge_service import KnowledgeBaseService
from apps.knowledge.domain.kb import KnowledgeBase

pytestmark = pytest.mark.unit


def _kb() -> KnowledgeBase:
    return KnowledgeBase(
        id=7,
        uuid="kb-7",
        name="KB7",
        description="",
        qdrant_collection_name="collection-7",
        created_at=None,
        updated_at=None,
    )


def test_current_strength_uses_decay():
    now = datetime.now(UTC).replace(tzinfo=None)
    item_recent = {
        "semantic_match": 0.3,
        "entity_match": 0.3,
        "time_match": 0.3,
        "place_match": 0.3,
        "graph_proximity": 0.3,
        "strength": 0.9,
        "baseline_strength": 0.05,
        "decay_rate": 0.02,
        "last_reinforced_at": now.isoformat(),
        "confidence": 0.6,
        "recency": 0.5,
        "status": "active",
    }
    item_old = {
        **item_recent,
        "last_reinforced_at": (now - timedelta(days=120)).isoformat(),
    }
    assert compute_final_score(item_recent) > compute_final_score(item_old)


def test_retrieval_hit_creates_reinforcement_event():
    repo = MagicMock()
    repo.list_all.return_value = [_kb()]
    repo.get_allowed_kb_ids_for_user.return_value = [7]
    repo.search_entity_candidates.return_value = []
    repo.get_assertion_neighbors.return_value = []
    repo.list_evidence_sentences.return_value = []
    repo.list_chunks_for_sentence_ids.return_value = []
    repo.get_entities_by_ids.return_value = []
    qdrant = MagicMock()
    qdrant.search_points = AsyncMock(
        side_effect=[
            [{"id": "assertion-11", "score": 0.9, "payload": {"text": "A", "source_point_id": "p1", "entity_ids": []}}],
            [],
            [],
            [],
            [],
        ]
    )
    svc = KnowledgeBaseService(repo=repo, qdrant_service=qdrant, user_repo=None, indexing_pipeline=None)
    hit_events: list[tuple[str, int, str]] = []

    def _reinforce(kb_uuid: str, assertion_id: int, event_type: str = "CHAT_RETRIEVAL_HIT"):
        hit_events.append((kb_uuid, assertion_id, event_type))
        return {"status": "ok"}

    svc.reinforce_assertion = _reinforce  # type: ignore[assignment]
    asyncio.run(
        svc.build_context_for_chat(
            question="mi történt?",
            current_user_id=1,
            current_user_role="user",
            parsed_query={
                "intent": "summary",
                "entity_candidates": [],
                "time_candidates": [],
                "place_candidates": [],
                "predicate_candidates": [],
                "retrieval_mode": "assertion_first",
            },
        )
    )
    assert hit_events
    assert hit_events[0][2] == "CHAT_RETRIEVAL_HIT"


def test_new_source_increases_source_diversity():
    class _FakeRepo:
        def __init__(self):
            self.sid = 1
            self.cid = 1
            self.assertions: dict[str, dict] = {}

        def create_sentence_batch(self, kb_id, source_point_id, rows):
            out = []
            for i, row in enumerate(rows):
                out.append({"id": self.sid, "sentence_order": i, "sanitized_text": row["sanitized_text"], "token_count": row["token_count"]})
                self.sid += 1
            return out

        def create_structural_chunk_batch(self, kb_id, source_point_id, rows):
            out = []
            for i, row in enumerate(rows):
                out.append({"id": self.cid, "chunk_order": i, "text": row["text"], "sentence_ids": row["sentence_ids"], "token_count": row["token_count"]})
                self.cid += 1
            return out

        def update_sentence_enrichment_batch(self, kb_id, rows): return len(rows)
        def update_structural_chunk_enrichment_batch(self, kb_id, rows): return len(rows)
        def create_mentions_batch(self, sentence_id, rows): return []
        def upsert_entity(self, kb_id, payload): return {"id": 1, "canonical_name": "Anna", "entity_type": "PERSON"}
        def upsert_time_interval(self, kb_id, payload): return {"id": 1}
        def upsert_place(self, kb_id, payload): return {"id": 1}
        def add_assertion_evidence(self, **kwargs): return None
        def add_reinforcement_event(self, **kwargs): return None
        def create_assertion_relations_batch(self, kb_id, rows): return 0

        def upsert_assertion(self, kb_id, payload):
            fp = payload["assertion_fingerprint"]
            src = payload["source_point_id"]
            if fp in self.assertions:
                row = self.assertions[fp]
                seen = row.setdefault("_seen_sources", {row["source_point_id"]})
                if src not in seen:
                    row["source_diversity"] = int(row.get("source_diversity", 1) + 1)
                    seen.add(src)
                row["created"] = False
                return row
            row = {**payload, "id": 1, "source_diversity": 1, "created": True, "_seen_sources": {src}}
            self.assertions[fp] = row
            return row

    class _Vec:
        async def ensure_collection_schema(self, collection): return None
        async def upsert_sentence_points(self, collection, rows): return None
        async def upsert_structural_chunk_points(self, collection, rows): return None
        async def upsert_assertion_points(self, collection, rows): return None
        async def upsert_entity_points(self, collection, rows): return None
        async def search_points(self, *args, **kwargs): return []
        async def delete_points_by_ids(self, collection, point_ids): return None
        async def delete_points_by_source_point_id(self, collection, source_point_id): return None

    class _Extractor:
        async def extract(self, sanitized_text: str, title: str | None = None) -> dict:
            _ = (sanitized_text, title)
            return {
                "entities": [{"canonical_name": "Anna", "entity_type": "PERSON", "aliases": [], "confidence": 0.8}],
                "mentions": [],
                "assertions": [{"subject": "Anna", "predicate": "dolgozik", "source_sentence_index": 0, "canonical_text": "Anna dolgozik", "confidence": 0.8}],
            }

    repo = _FakeRepo()
    pipe = KnowledgeIndexingPipeline(repo=repo, vector_index=_Vec(), extractor=_Extractor())
    asyncio.run(pipe.index_training_content(1, "kb-1", "c1", "src-1", "Anna dolgozik.", "t"))
    asyncio.run(pipe.index_training_content(1, "kb-1", "c1", "src-2", "Anna dolgozik.", "t"))
    assertion = next(iter(repo.assertions.values()))
    assert assertion["source_diversity"] == 2


def test_query_parser_detects_timeline_intent():
    parser = QueryParser()
    parsed = parser.parse("Mutasd időrendben hogyan változott Anna státusza 2023 és 2024 között")
    assert parsed["intent"] == "timeline"
    assert parsed["retrieval_mode"] == "timeline_first"


def test_query_parser_detects_comparison_intent():
    parser = QueryParser()
    parsed = parser.parse("Hasonlítsd össze Anna és Béla teljesítményét 2023-ban és 2024-ben")
    assert parsed["intent"] == "comparison"
    assert parsed["retrieval_mode"] == "comparison_first"
    assert len(parsed["comparison_targets"]) >= 2


def test_context_builder_groups_by_time_slice():
    builder = KnowledgeContextBuilder()
    packet = builder.build_context_packet(
        assertion_hits=[
            {"id": "assertion-1", "text": "A", "entity_ids": [1], "time_from": "2024-01-01", "time_to": "2024-01-31",
             "semantic_match": 0.8, "entity_match": 0.8, "time_match": 0.8, "place_match": 0.0, "graph_proximity": 0.5,
             "strength": 0.6, "confidence": 0.7, "recency": 0.5},
            {"id": "assertion-2", "text": "B", "entity_ids": [1], "time_from": "2024-01-15", "time_to": "2024-02-01",
             "semantic_match": 0.7, "entity_match": 0.7, "time_match": 0.7, "place_match": 0.0, "graph_proximity": 0.4,
             "strength": 0.5, "confidence": 0.7, "recency": 0.5},
        ],
        sentence_hits=[],
        chunk_hits=[],
        query_focus={"intent": "timeline", "retrieval_mode": "timeline_first"},
    )
    assert len(packet["time_slice_groups"]) >= 1


def test_context_builder_groups_by_entity():
    builder = KnowledgeContextBuilder()
    packet = builder.build_context_packet(
        assertion_hits=[
            {"id": "assertion-1", "text": "A", "entity_ids": [11], "predicate": "dolgozik",
             "semantic_match": 0.8, "entity_match": 0.8, "time_match": 0.8, "place_match": 0.0, "graph_proximity": 0.5,
             "strength": 0.6, "confidence": 0.7, "recency": 0.5},
        ],
        sentence_hits=[],
        chunk_hits=[],
    )
    assert len(packet["per_entity_assertion_groups"]) >= 1
    assert packet["per_entity_assertion_groups"][0]["entity_id"] == 11


def test_context_builder_outputs_dynamic_chunks():
    builder = KnowledgeContextBuilder()
    packet = builder.build_context_packet(
        assertion_hits=[
            {
                "id": "assertion-1",
                "text": "Anna dolgozik Budapesten",
                "entity_ids": [11],
                "predicate": "dolgozik",
                "time_from": "2024-01-01",
                "time_to": "2024-01-31",
                "place_keys": ["budapest"],
                "semantic_match": 0.8,
                "entity_match": 0.8,
                "time_match": 0.8,
                "place_match": 0.8,
                "graph_proximity": 0.5,
                "strength": 0.6,
                "confidence": 0.7,
                "recency": 0.5,
            },
            {
                "id": "assertion-2",
                "text": "Anna vezeti a csapatot Budapesten",
                "entity_ids": [11],
                "predicate": "vezet",
                "time_from": "2024-01-01",
                "time_to": "2024-01-31",
                "place_keys": ["budapest"],
                "semantic_match": 0.75,
                "entity_match": 0.8,
                "time_match": 0.8,
                "place_match": 0.8,
                "graph_proximity": 0.5,
                "strength": 0.55,
                "confidence": 0.7,
                "recency": 0.5,
            },
        ],
        sentence_hits=[],
        chunk_hits=[],
    )
    assert packet["dynamic_chunks"]
    assert len(packet["dynamic_chunks"][0]["assertion_ids"]) >= 1


def test_comparison_context_builds_two_branches():
    builder = KnowledgeContextBuilder()
    packet = builder.build_context_packet(
        assertion_hits=[
            {"id": "assertion-1", "text": "Anna vezet", "entity_ids": [1], "semantic_match": 0.8, "entity_match": 0.8,
             "time_match": 0.8, "place_match": 0.0, "graph_proximity": 0.5, "strength": 0.6, "confidence": 0.7, "recency": 0.5},
            {"id": "assertion-2", "text": "Béla vezet", "entity_ids": [2], "semantic_match": 0.8, "entity_match": 0.8,
             "time_match": 0.8, "place_match": 0.0, "graph_proximity": 0.5, "strength": 0.6, "confidence": 0.7, "recency": 0.5},
        ],
        sentence_hits=[],
        chunk_hits=[],
        query_focus={"intent": "comparison", "comparison_targets": ["Anna", "Béla"], "retrieval_mode": "comparison_first"},
    )
    assert packet["comparison_summary"]["enabled"] is True
    assert len(packet["comparison_left"]) >= 1
    assert len(packet["comparison_right"]) >= 1


def test_uncertain_assertion_is_ranked_lower():
    high = compute_final_score(
        {
            "semantic_match": 0.6,
            "entity_match": 0.6,
            "time_match": 0.6,
            "place_match": 0.6,
            "graph_proximity": 0.6,
            "strength": 0.6,
            "baseline_strength": 0.05,
            "decay_rate": 0.015,
            "last_reinforced_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
            "confidence": 0.6,
            "recency": 0.6,
            "status": "active",
        }
    )
    low = compute_final_score(
        {
            "semantic_match": 0.6,
            "entity_match": 0.6,
            "time_match": 0.6,
            "place_match": 0.6,
            "graph_proximity": 0.6,
            "strength": 0.6,
            "baseline_strength": 0.05,
            "decay_rate": 0.015,
            "last_reinforced_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
            "confidence": 0.6,
            "recency": 0.6,
            "status": "uncertain",
        }
    )
    assert low < high
