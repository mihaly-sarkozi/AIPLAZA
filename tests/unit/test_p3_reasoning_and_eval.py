from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import pytest

from apps.knowledge.application.context_builder import KnowledgeContextBuilder
from apps.knowledge.application.evaluation import RetrievalEvaluationService
from apps.knowledge.application.indexing_pipeline import KnowledgeIndexingPipeline
from apps.knowledge.application.maintenance import KnowledgeMaintenanceService
from apps.knowledge.application.reranker import compute_final_score

pytestmark = pytest.mark.unit


class _Vec:
    async def ensure_collection_schema(self, collection): return None
    async def upsert_sentence_points(self, collection, rows): return None
    async def upsert_structural_chunk_points(self, collection, rows): return None
    async def upsert_assertion_points(self, collection, rows): return None
    async def upsert_entity_points(self, collection, rows): return None
    async def search_points(self, *args, **kwargs): return []
    async def delete_points_by_ids(self, collection, point_ids): return None
    async def delete_points_by_source_point_id(self, collection, source_point_id): return None


class _Repo:
    def __init__(self):
        self.sid = 1
        self.cid = 1
        self.aid = 1
        self._assertions: list[dict] = []
        self.relations: list[dict] = []

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

    def create_mentions_batch(self, sentence_id, rows): return []
    def update_sentence_enrichment_batch(self, kb_id, rows): return len(rows)
    def update_structural_chunk_enrichment_batch(self, kb_id, rows): return len(rows)
    def upsert_entity(self, kb_id, payload): return {"id": 11, "canonical_name": payload.get("canonical_name"), "entity_type": payload.get("entity_type", "PERSON")}
    def upsert_time_interval(self, kb_id, payload): return {"id": 1}
    def upsert_place(self, kb_id, payload): return {"id": 1}
    def add_assertion_evidence(self, **kwargs): return None
    def add_reinforcement_event(self, **kwargs): return None
    def update_assertion_status(self, kb_id, assertion_id, status): return True

    def upsert_assertion(self, kb_id, payload):
        row = dict(payload)
        row["id"] = self.aid
        self.aid += 1
        row["created"] = True
        self._assertions.append(row)
        return row

    def create_assertion_relations_batch(self, kb_id, rows):
        self.relations.extend(rows)
        return len(rows)


class _ExtractorRefineConflict:
    async def extract(self, sanitized_text: str, title: str | None = None) -> dict:
        _ = (sanitized_text, title)
        return {
            "entities": [{"canonical_name": "Péter", "entity_type": "PERSON", "aliases": [], "confidence": 0.9}],
            "mentions": [],
            "assertions": [
                {
                    "subject": "Péter",
                    "predicate": "dolgozik",
                    "object_value": "ProjektX",
                    "source_sentence_index": 0,
                    "canonical_text": "Péter 2023-ban dolgozott ProjektX-en",
                    "time_from": "2023-01-01T00:00:00",
                    "time_to": "2023-12-31T00:00:00",
                    "confidence": 0.9,
                },
                {
                    "subject": "Péter",
                    "predicate": "dolgozik",
                    "object_value": "ProjektX",
                    "source_sentence_index": 1,
                    "canonical_text": "Péter 2023 július-szeptemberben dolgozott ProjektX-en",
                    "time_from": "2023-07-01T00:00:00",
                    "time_to": "2023-09-30T00:00:00",
                    "confidence": 0.9,
                },
            ],
        }


def test_refines_relation_created_for_more_specific_time_assertion():
    repo = _Repo()
    pipe = KnowledgeIndexingPipeline(repo=repo, vector_index=_Vec(), extractor=_ExtractorRefineConflict())
    asyncio.run(pipe.index_training_content(1, "kb-1", "c1", "src-1", "Péter dolgozik.", "t"))
    assert any(str(r.get("relation_type")) == "REFINES" for r in repo.relations)


def test_conflicting_assertions_marked_as_conflicted():
    builder = KnowledgeContextBuilder()
    packet = builder.build_context_packet(
        assertion_hits=[
            {"id": "assertion-1", "text": "A projekt aktív", "status": "conflicted", "relation_type": "CONTRADICTS",
             "entity_ids": [1], "predicate": "status", "semantic_match": 0.8, "entity_match": 0.8, "time_match": 0.8,
             "place_match": 0.0, "graph_proximity": 0.5, "strength": 0.6, "confidence": 0.7, "recency": 0.5},
            {"id": "assertion-2", "text": "A projekt lezárt", "status": "conflicted", "relation_type": "CONTRADICTS",
             "entity_ids": [1], "predicate": "status", "semantic_match": 0.79, "entity_match": 0.8, "time_match": 0.8,
             "place_match": 0.0, "graph_proximity": 0.5, "strength": 0.6, "confidence": 0.7, "recency": 0.5},
        ],
        sentence_hits=[],
        chunk_hits=[],
    )
    assert len(packet["conflicting_assertions"]) >= 2
    assert len(packet["conflict_bundles"]) >= 1


def test_supporting_assertions_increase_effective_rank():
    base = {
        "semantic_match": 0.5, "entity_match": 0.5, "time_match": 0.5, "place_match": 0.1, "graph_proximity": 0.1,
        "strength": 0.4, "baseline_strength": 0.05, "decay_rate": 0.015,
        "last_reinforced_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
        "confidence": 0.6, "recency": 0.5, "status": "active",
    }
    supported = dict(base)
    supported["relation_type"] = "SUPPORTS"
    supported["relation_weight"] = 0.85
    assert compute_final_score(supported) > compute_final_score(base)


def test_superseded_assertion_ranked_lower_than_refined_one():
    now = datetime.now(UTC).replace(tzinfo=None).isoformat()
    refined = compute_final_score(
        {"semantic_match": 0.6, "entity_match": 0.6, "time_match": 0.6, "place_match": 0.2, "graph_proximity": 0.5,
         "strength": 0.6, "baseline_strength": 0.05, "decay_rate": 0.015, "last_reinforced_at": now,
         "confidence": 0.65, "recency": 0.5, "status": "refined"}
    )
    superseded = compute_final_score(
        {"semantic_match": 0.6, "entity_match": 0.6, "time_match": 0.6, "place_match": 0.2, "graph_proximity": 0.5,
         "strength": 0.6, "baseline_strength": 0.05, "decay_rate": 0.015, "last_reinforced_at": now,
         "confidence": 0.65, "recency": 0.5, "status": "superseded"}
    )
    assert refined > superseded


def test_retrieval_eval_script_runs_on_dataset(tmp_path):
    dataset = tmp_path / "eval.json"
    dataset.write_text(
        json.dumps(
            [{"query": "Mi történt?", "expected_keywords": ["projekt"], "intent": "summary"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class _Retrieval:
        async def build_context_for_chat(self, **kwargs):
            _ = kwargs
            return {
                "top_assertions": [{"id": "assertion-1", "entity_ids": [11]}],
                "evidence_sentences": [{"text": "projekt fut"}],
                "source_chunks": [],
                "query_focus": {"time_window": {}},
                "scoring_summary": {},
            }

    svc = RetrievalEvaluationService(retrieval_service=_Retrieval())
    out = asyncio.run(
        svc.run_retrieval_eval(
            dataset_path=str(dataset),
            kb_uuid="kb-1",
            current_user_id=1,
            current_user_role="owner",
        )
    )
    assert out["cases"] == 1
    assert "metrics" in out and "entity_recall" in out["metrics"]


def test_context_builder_outputs_conflict_bundle():
    builder = KnowledgeContextBuilder()
    packet = builder.build_context_packet(
        assertion_hits=[
            {"id": "assertion-1", "text": "X aktív", "status": "conflicted", "relation_type": "CONTRADICTS",
             "entity_ids": [3], "predicate": "állapot", "semantic_match": 0.8, "entity_match": 0.8, "time_match": 0.8,
             "place_match": 0.0, "graph_proximity": 0.5, "strength": 0.6, "confidence": 0.7, "recency": 0.5},
            {"id": "assertion-2", "text": "X lezárt", "status": "conflicted", "relation_type": "CONTRADICTS",
             "entity_ids": [3], "predicate": "állapot", "semantic_match": 0.79, "entity_match": 0.8, "time_match": 0.8,
             "place_match": 0.0, "graph_proximity": 0.5, "strength": 0.6, "confidence": 0.7, "recency": 0.5},
        ],
        sentence_hits=[],
        chunk_hits=[],
    )
    assert packet["conflict_bundles"]


def test_timeline_packet_is_chronologically_sorted():
    builder = KnowledgeContextBuilder()
    packet = builder.build_context_packet(
        assertion_hits=[
            {"id": "assertion-2", "text": "későbbi", "entity_ids": [1], "time_from": "2024-02-01",
             "semantic_match": 0.8, "entity_match": 0.8, "time_match": 0.8, "place_match": 0.0, "graph_proximity": 0.5,
             "strength": 0.6, "confidence": 0.7, "recency": 0.5},
            {"id": "assertion-1", "text": "korábbi", "entity_ids": [1], "time_from": "2024-01-01",
             "semantic_match": 0.7, "entity_match": 0.8, "time_match": 0.8, "place_match": 0.0, "graph_proximity": 0.5,
             "strength": 0.6, "confidence": 0.7, "recency": 0.5},
        ],
        sentence_hits=[],
        chunk_hits=[],
        query_focus={"intent": "timeline", "retrieval_mode": "timeline_first"},
    )
    timeline = packet["timeline_sequence"]
    assert timeline[0]["time_from"] <= timeline[1]["time_from"]


def test_configurable_rerank_weights_are_applied():
    base = {
        "semantic_match": 0.5, "entity_match": 0.1, "time_match": 0.1, "place_match": 0.0, "graph_proximity": 0.0,
        "strength": 0.2, "baseline_strength": 0.05, "decay_rate": 0.015,
        "last_reinforced_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
        "confidence": 0.2, "recency": 0.2, "status": "active",
    }
    boosted = dict(base)
    boosted["weights"] = {"semantic_match": 0.7, "entity_match": 0.01}
    assert compute_final_score(boosted) != compute_final_score(base)


def test_assertion_debug_shows_relations_evidence_status():
    class _RepoForDebug:
        def get_by_uuid(self, uuid): return type("KB", (), {"id": 7, "uuid": uuid})()
        def get_assertion_debug(self, kb_id, assertion_id):
            _ = (kb_id, assertion_id)
            return {
                "assertion": {"id": assertion_id, "status": "conflicted"},
                "relations": [{"relation_type": "CONTRADICTS"}],
                "evidence": [{"sentence_id": 1}],
                "mentions": [{"surface_form": "Péter"}],
            }

    svc = KnowledgeMaintenanceService(kb_service=None, repo=_RepoForDebug())
    dbg = svc.get_assertion_debug("kb-7", 99)
    assert dbg["assertion"]["status"] == "conflicted"
    assert dbg["relations"]
    assert dbg["evidence"]
