from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.knowledge.application.context_builder import KnowledgeContextBuilder
from apps.knowledge.application.indexing_pipeline import KnowledgeIndexingPipeline
from apps.knowledge.application.knowledge_service import KnowledgeBaseService
from apps.knowledge.domain.kb import KnowledgeBase

pytestmark = pytest.mark.unit


class _RepoForP1:
    def __init__(self):
        self.sid = 1
        self.cid = 1
        self.eid = 1
        self.aid = 1
        self.tid = 1
        self.mentions: list[dict] = []
        self.relations: list[dict] = []
        self.entities: dict[str, dict] = {}
        self.assertions: dict[str, dict] = {}

    def create_sentence_batch(self, kb_id, source_point_id, rows):
        out = []
        for i, row in enumerate(rows):
            rec = dict(row)
            rec["id"] = self.sid
            rec["kb_id"] = kb_id
            rec["source_point_id"] = source_point_id
            rec["sentence_order"] = int(row.get("sentence_order", i))
            self.sid += 1
            out.append(rec)
        return out

    def create_structural_chunk_batch(self, kb_id, source_point_id, rows):
        out = []
        for i, row in enumerate(rows):
            rec = dict(row)
            rec["id"] = self.cid
            rec["kb_id"] = kb_id
            rec["source_point_id"] = source_point_id
            rec["chunk_order"] = int(row.get("chunk_order", i))
            self.cid += 1
            out.append(rec)
        return out

    def update_sentence_enrichment_batch(self, kb_id, rows):
        _ = (kb_id, rows)
        return len(rows)

    def update_structural_chunk_enrichment_batch(self, kb_id, rows):
        _ = (kb_id, rows)
        return len(rows)

    def create_mentions_batch(self, sentence_id, rows):
        out = []
        for row in rows:
            rec = dict(row)
            rec["id"] = len(self.mentions) + 1
            rec["sentence_id"] = sentence_id
            self.mentions.append(rec)
            out.append(rec)
        return out

    def upsert_entity(self, kb_id, payload):
        key = (payload.get("canonical_name") or "").lower()
        if key in self.entities:
            return self.entities[key]
        rec = {
            "id": self.eid,
            "kb_id": kb_id,
            "canonical_name": payload.get("canonical_name"),
            "canonical_key": f"{(payload.get('entity_type') or 'UNKNOWN').lower()}::{key}",
            "entity_type": payload.get("entity_type"),
            "aliases": payload.get("aliases") or [],
            "confidence": payload.get("confidence") or 0.0,
        }
        self.entities[key] = rec
        self.eid += 1
        return rec

    def upsert_time_interval(self, kb_id, payload):
        rec = dict(payload)
        rec["id"] = self.tid
        self.tid += 1
        return rec

    def upsert_place(self, kb_id, payload):
        rec = dict(payload)
        rec["id"] = 1
        return rec

    def upsert_assertion(self, kb_id, payload):
        fp = payload["assertion_fingerprint"]
        if fp in self.assertions:
            rec = self.assertions[fp]
            rec["created"] = False
            return rec
        rec = dict(payload)
        rec["id"] = self.aid
        rec["created"] = True
        self.aid += 1
        self.assertions[fp] = rec
        return rec

    def add_assertion_evidence(self, **kwargs):
        _ = kwargs
        return None

    def add_reinforcement_event(self, **kwargs):
        _ = kwargs
        return None

    def create_assertion_relations_batch(self, kb_id, rows):
        _ = kb_id
        self.relations.extend(rows)
        return len(rows)


class _VectorForP1:
    def __init__(self):
        self.points = {"entity": [], "assertion": [], "sentence": [], "chunk": []}

    async def ensure_collection_schema(self, collection):
        _ = collection

    async def upsert_entity_points(self, collection, rows):
        _ = collection
        self.points["entity"].extend(rows)

    async def upsert_assertion_points(self, collection, rows):
        _ = collection
        self.points["assertion"].extend(rows)

    async def upsert_sentence_points(self, collection, rows):
        _ = collection
        self.points["sentence"].extend(rows)

    async def upsert_structural_chunk_points(self, collection, rows):
        _ = collection
        self.points["chunk"].extend(rows)

    async def search_points(self, collection, query, limit=10, point_types=None, payload_filter=None):
        _ = (collection, query, limit, point_types, payload_filter)
        return []

    async def delete_points_by_ids(self, collection, point_ids):
        _ = (collection, point_ids)

    async def delete_points_by_source_point_id(self, collection, source_point_id):
        _ = (collection, source_point_id)


def _kb() -> KnowledgeBase:
    return KnowledgeBase(
        id=2,
        uuid="kb-2",
        name="KB",
        description="",
        qdrant_collection_name="collection-2",
        created_at=None,
        updated_at=None,
    )


def test_mentions_created_from_extraction():
    repo = _RepoForP1()
    vector = _VectorForP1()

    class _Extractor:
        async def extract(self, sanitized_text: str, title: str | None = None) -> dict:
            _ = (sanitized_text, title)
            return {
                "entities": [{"canonical_name": "Péter", "entity_type": "PERSON", "aliases": [], "confidence": 0.9}],
                "mentions": [
                    {
                        "surface_form": "Péter",
                        "mention_type": "person",
                        "grammatical_role": "subject",
                        "source_sentence_index": 0,
                        "resolved_entity_candidate_name": "Péter",
                        "resolution_confidence": 0.95,
                        "is_implicit_subject": False,
                    }
                ],
                "assertions": [],
            }

    pipeline = KnowledgeIndexingPipeline(repo=repo, vector_index=vector, extractor=_Extractor())
    asyncio.run(
        pipeline.index_training_content(
            kb_id=2,
            kb_uuid="kb-2",
            collection="collection-2",
            source_point_id="p1",
            sanitized_text="Péter ma dolgozik.",
            title="t",
        )
    )
    assert len(repo.mentions) >= 1


def test_implicit_subject_mention_created():
    repo = _RepoForP1()
    vector = _VectorForP1()

    class _Extractor:
        async def extract(self, sanitized_text: str, title: str | None = None) -> dict:
            _ = (sanitized_text, title)
            return {
                "entities": [],
                "mentions": [],
                "assertions": [
                    {
                        "subject": "<implicit_subject>",
                        "subject_is_implicit": True,
                        "predicate": "dolgozik",
                        "object": None,
                        "source_sentence_index": 0,
                        "canonical_text": "Dolgozik",
                        "confidence": 0.6,
                    }
                ],
            }

    pipeline = KnowledgeIndexingPipeline(repo=repo, vector_index=vector, extractor=_Extractor())
    asyncio.run(
        pipeline.index_training_content(
            kb_id=2,
            kb_uuid="kb-2",
            collection="collection-2",
            source_point_id="p1",
            sanitized_text="Dolgozik a projekten.",
            title="t",
        )
    )
    assert any(m.get("surface_form") == "<implicit_subject>" for m in repo.mentions)


def test_entity_alias_resolution_merges_candidates():
    repo = MagicMock()
    repo.list_all.return_value = [_kb()]
    repo.get_allowed_kb_ids_for_user.return_value = [2]
    repo.search_entity_candidates.side_effect = [
        [{"id": 101, "canonical_name": "Péter Kovács", "entity_type": "PERSON", "aliases": ["Kovács Péter"], "confidence": 0.8}],
        [{"id": 101, "canonical_name": "Péter Kovács", "entity_type": "PERSON", "aliases": ["Kovács Péter"], "confidence": 0.8}],
    ]
    repo.list_evidence_sentences.return_value = []
    repo.list_chunks_for_sentence_ids.return_value = []
    repo.get_entities_by_ids.return_value = []
    repo.get_assertion_neighbors.return_value = []
    qdrant = MagicMock()
    qdrant.search_points = AsyncMock(return_value=[])

    svc = KnowledgeBaseService(repo=repo, qdrant_service=qdrant, user_repo=None, indexing_pipeline=None)
    packet = asyncio.run(
        svc.build_context_for_chat(
            question="Mit csinált Kovács Péter?",
            current_user_id=7,
            current_user_role="user",
            parsed_query={
                "intent": "activity",
                "entity_candidates": ["Péter", "Kovács Péter"],
                "time_candidates": [],
                "place_candidates": [],
                "predicate_candidates": [],
            },
        )
    )
    resolved = packet["query_focus"]["resolved_entity_candidates"]["kb-2"]
    assert len(resolved) == 1
    assert resolved[0]["entity_id"] == 101


def test_query_entity_resolution_uses_alias_and_qdrant():
    repo = MagicMock()
    repo.list_all.return_value = [_kb()]
    repo.get_allowed_kb_ids_for_user.return_value = [2]
    repo.search_entity_candidates.return_value = [
        {"id": 201, "canonical_name": "ProjektX", "entity_type": "PROJECT", "aliases": ["Project X"], "confidence": 0.7}
    ]
    repo.list_evidence_sentences.return_value = []
    repo.list_chunks_for_sentence_ids.return_value = []
    repo.get_entities_by_ids.return_value = []
    repo.get_assertion_neighbors.return_value = []
    qdrant = MagicMock()
    qdrant.search_points = AsyncMock(
        side_effect=[
            [{"id": "entity-202", "score": 0.9, "payload": {"entity_id": 202, "canonical_name": "X Projekt", "entity_type": "PROJECT"}}],
            [],
            [],
            [],
        ]
    )

    svc = KnowledgeBaseService(repo=repo, qdrant_service=qdrant, user_repo=None, indexing_pipeline=None)
    packet = asyncio.run(
        svc.build_context_for_chat(
            question="Mi a helyzet ProjektX-szel?",
            current_user_id=7,
            current_user_role="user",
            parsed_query={
                "intent": "summary",
                "entity_candidates": ["ProjektX"],
                "time_candidates": [],
                "place_candidates": [],
                "predicate_candidates": [],
            },
        )
    )
    resolved = packet["query_focus"]["resolved_entity_candidates"]["kb-2"]
    ids = {x["entity_id"] for x in resolved}
    assert 201 in ids
    assert 202 in ids


def test_assertion_relations_created_for_same_subject_and_time():
    repo = _RepoForP1()
    vector = _VectorForP1()

    class _Extractor:
        async def extract(self, sanitized_text: str, title: str | None = None) -> dict:
            _ = (sanitized_text, title)
            return {
                "entities": [{"canonical_name": "Anna", "entity_type": "PERSON", "aliases": [], "confidence": 0.9}],
                "mentions": [],
                "assertions": [
                    {
                        "subject": "Anna",
                        "predicate": "dolgozik",
                        "source_sentence_index": 0,
                        "time_from": "2024-01-01",
                        "time_to": "2024-02-01",
                        "canonical_text": "Anna dolgozik",
                        "confidence": 0.8,
                    },
                    {
                        "subject": "Anna",
                        "predicate": "vezet",
                        "source_sentence_index": 1,
                        "time_from": "2024-01-15",
                        "time_to": "2024-03-01",
                        "canonical_text": "Anna vezet",
                        "confidence": 0.8,
                    },
                ],
            }

    pipeline = KnowledgeIndexingPipeline(repo=repo, vector_index=vector, extractor=_Extractor())
    out = asyncio.run(
        pipeline.index_training_content(
            kb_id=2,
            kb_uuid="kb-2",
            collection="collection-2",
            source_point_id="p1",
            sanitized_text="Anna dolgozik. Anna vezet.",
            title="t",
        )
    )
    assert out["relation_count"] > 0
    rel_types = {r["relation_type"] for r in repo.relations}
    assert "SAME_SUBJECT" in rel_types
    assert "TEMPORALLY_OVERLAPS" in rel_types


def test_neighbor_expansion_uses_assertion_relations():
    repo = MagicMock()
    repo.list_all.return_value = [_kb()]
    repo.get_allowed_kb_ids_for_user.return_value = [2]
    repo.search_entity_candidates.return_value = []
    repo.get_assertion_neighbors.return_value = [
        {
            "assertion_id": 999,
            "canonical_text": "Szomszéd assertion",
            "predicate": "vezet",
            "source_point_id": "sp-1",
            "time_from": None,
            "time_to": None,
            "place_key": None,
            "subject_entity_id": 10,
            "object_entity_id": None,
            "relation_type": "SAME_SUBJECT",
            "relation_weight": 0.9,
            "depth": 1,
            "confidence": 0.8,
            "strength": 0.7,
        }
    ]
    repo.list_evidence_sentences.return_value = []
    repo.list_chunks_for_sentence_ids.return_value = []
    repo.get_entities_by_ids.return_value = []
    qdrant = MagicMock()
    qdrant.search_points = AsyncMock(
        side_effect=[
            [{"id": "assertion-1", "score": 0.9, "payload": {"text": "Seed", "source_point_id": "sp-1", "entity_ids": [10], "predicate": "dolgozik"}}],
            [],
            [],
            [],
            [],
        ]
    )
    svc = KnowledgeBaseService(repo=repo, qdrant_service=qdrant, user_repo=None, indexing_pipeline=None)
    packet = asyncio.run(
        svc.build_context_for_chat(
            question="Mit csinál?",
            current_user_id=5,
            current_user_role="user",
            parsed_query={
                "intent": "activity",
                "entity_candidates": [],
                "time_candidates": [],
                "place_candidates": [],
                "predicate_candidates": [],
            },
        )
    )
    assert any(x.get("relation_type") == "SAME_SUBJECT" for x in packet.get("expanded_assertions") or [])


def test_context_builder_outputs_seed_and_expanded_groups():
    builder = KnowledgeContextBuilder()
    packet = builder.build_context_packet(
        assertion_hits=[
            {
                "id": "assertion-1",
                "text": "Seed",
                "is_seed": True,
                "entity_ids": [10],
                "time_from": "2024-01-01T00:00:00",
                "time_to": "2024-01-31T23:59:59",
                "semantic_match": 0.9,
                "entity_match": 0.9,
                "time_match": 0.9,
                "place_match": 0.0,
                "graph_proximity": 0.4,
                "strength": 0.6,
                "confidence": 0.7,
                "recency": 0.5,
            },
            {
                "id": "assertion-2",
                "text": "Expanded",
                "is_seed": False,
                "relation_type": "SAME_SUBJECT",
                "relation_weight": 0.9,
                "entity_ids": [10],
                "time_from": "2024-01-15T00:00:00",
                "time_to": "2024-02-15T00:00:00",
                "semantic_match": 0.4,
                "entity_match": 0.8,
                "time_match": 0.8,
                "place_match": 0.0,
                "graph_proximity": 0.9,
                "strength": 0.5,
                "confidence": 0.7,
                "recency": 0.5,
            },
        ],
        sentence_hits=[],
        chunk_hits=[],
    )
    assert len(packet["seed_assertions"]) == 1
    assert len(packet["expanded_assertions"]) == 1
    assert len(packet["time_slice_groups"]) >= 1
