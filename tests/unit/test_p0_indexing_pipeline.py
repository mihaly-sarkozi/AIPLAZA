from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from apps.knowledge.application.indexing_pipeline import KnowledgeIndexingPipeline

pytestmark = pytest.mark.unit


class _FakeRepo:
    def __init__(self):
        self._sentence_id = 1
        self._chunk_id = 1
        self._entity_id = 1
        self._time_id = 1
        self._place_id = 1
        self._assertion_id = 1
        self.sentences: list[dict] = []
        self.chunks: list[dict] = []
        self.entities: dict[str, dict] = {}
        self.times: list[dict] = []
        self.assertions_by_fp: dict[str, dict] = {}
        self.evidences: list[dict] = []

    def create_sentence_batch(self, kb_id: int, source_point_id: str, rows: list[dict]) -> list[dict]:
        out = []
        for row in rows:
            item = dict(row)
            item["id"] = self._sentence_id
            item["kb_id"] = kb_id
            item["source_point_id"] = source_point_id
            self._sentence_id += 1
            self.sentences.append(item)
            out.append(item)
        return out

    def create_structural_chunk_batch(self, kb_id: int, source_point_id: str, rows: list[dict]) -> list[dict]:
        out = []
        for row in rows:
            item = dict(row)
            item["id"] = self._chunk_id
            item["kb_id"] = kb_id
            item["source_point_id"] = source_point_id
            self._chunk_id += 1
            self.chunks.append(item)
            out.append(item)
        return out

    def update_sentence_enrichment_batch(self, kb_id: int, rows: list[dict]) -> int:
        by_id = {int(x["id"]): x for x in self.sentences}
        for row in rows:
            if int(row["id"]) in by_id:
                by_id[int(row["id"])].update(dict(row))
        return len(rows)

    def update_structural_chunk_enrichment_batch(self, kb_id: int, rows: list[dict]) -> int:
        by_id = {int(x["id"]): x for x in self.chunks}
        for row in rows:
            if int(row["id"]) in by_id:
                by_id[int(row["id"])].update(dict(row))
        return len(rows)

    def upsert_entity(self, kb_id: int, payload: dict) -> dict:
        key = (payload.get("canonical_name") or "").lower()
        if key in self.entities:
            return self.entities[key]
        entity = {
            "id": self._entity_id,
            "kb_id": kb_id,
            "canonical_name": payload.get("canonical_name"),
            "entity_type": payload.get("entity_type"),
        }
        self.entities[key] = entity
        self._entity_id += 1
        return entity

    def upsert_time_interval(self, kb_id: int, payload: dict) -> dict:
        row = dict(payload)
        row["id"] = self._time_id
        self._time_id += 1
        self.times.append(row)
        return row

    def upsert_place(self, kb_id: int, payload: dict) -> dict:
        row = dict(payload)
        row["id"] = self._place_id
        self._place_id += 1
        return row

    def upsert_assertion(self, kb_id: int, payload: dict) -> dict:
        fp = payload["assertion_fingerprint"]
        if fp in self.assertions_by_fp:
            row = self.assertions_by_fp[fp]
            row["evidence_count"] = int(row.get("evidence_count", 1) + 1)
            row["created"] = False
            return row
        row = dict(payload)
        row["id"] = self._assertion_id
        row["created"] = True
        self._assertion_id += 1
        self.assertions_by_fp[fp] = row
        return row

    def add_assertion_evidence(
        self,
        kb_id: int,
        assertion_id: int,
        sentence_id: int,
        source_point_id: str,
        evidence_type: str = "PRIMARY",
        confidence: float | None = None,
        weight: float = 1.0,
    ) -> None:
        self.evidences.append(
            {
                "assertion_id": assertion_id,
                "sentence_id": sentence_id,
                "source_point_id": source_point_id,
                "evidence_type": evidence_type,
                "confidence": confidence,
                "weight": weight,
            }
        )

    def create_mentions_batch(self, sentence_id: int, rows: list[dict]) -> list[dict]:
        return rows

    def add_reinforcement_event(self, **kwargs) -> None:
        return None


class _FakeVectorIndex:
    def __init__(self):
        self.assertion_rows: list[dict] = []
        self.sentence_rows: list[dict] = []
        self.chunk_rows: list[dict] = []

    async def ensure_collection_schema(self, collection: str) -> None:
        return None

    async def upsert_assertion_points(self, collection: str, rows: list[dict]) -> None:
        self.assertion_rows.extend(rows)

    async def upsert_sentence_points(self, collection: str, rows: list[dict]) -> None:
        self.sentence_rows.extend(rows)

    async def upsert_structural_chunk_points(self, collection: str, rows: list[dict]) -> None:
        self.chunk_rows.extend(rows)

    async def upsert_entity_points(self, collection: str, rows: list[dict]) -> None:
        return None

    async def search_points(self, collection: str, query: str, limit: int = 10, point_types=None, payload_filter=None):
        return []

    async def delete_points_by_ids(self, collection: str, point_ids: list[str]) -> None:
        return None

    async def delete_points_by_source_point_id(self, collection: str, source_point_id: str) -> None:
        return None


class _FakeExtractor:
    async def extract(self, sanitized_text: str, title: str | None = None) -> dict:
        _ = (sanitized_text, title)
        return {
            "extraction_confidence": 0.8,
            "entities": [
                {"canonical_name": "Péter", "entity_type": "PERSON", "aliases": [], "confidence": 0.9},
                {"canonical_name": "ProjektX", "entity_type": "PROJECT", "aliases": [], "confidence": 0.9},
            ],
            "assertions": [
                {
                    "subject": "Péter",
                    "predicate": "dolgozik",
                    "object": "ProjektX",
                    "object_entity": "ProjektX",
                    "source_sentence_index": 0,
                    "time_from": "2023-06-01",
                    "time_to": "2023-08-31",
                    "place_key": "Budapest",
                    "attributes": [],
                    "canonical_text": "Péter dolgozik ProjektX",
                    "confidence": 0.85,
                }
            ],
            "time_candidates": [],
            "place_candidates": [],
        }


def test_time_fields_persisted_from_extractor():
    repo = _FakeRepo()
    vector = _FakeVectorIndex()
    pipeline = KnowledgeIndexingPipeline(repo=repo, vector_index=vector, extractor=_FakeExtractor())
    asyncio.run(
        pipeline.index_training_content(
            kb_id=1,
            kb_uuid="kb-1",
            collection="c1",
            source_point_id="p1",
            sanitized_text="Péter dolgozik ProjektX-ben 2023-06-01 és 2023-08-31 között.",
            title="t",
        )
    )
    assertion = next(iter(repo.assertions_by_fp.values()))
    assert assertion["time_from"] is not None
    assert assertion["time_to"] is not None
    assert isinstance(assertion["time_from"], datetime)
    assert vector.assertion_rows[0]["payload"]["time_from"] is not None
    assert vector.assertion_rows[0]["payload"]["time_to"] is not None


def test_sentence_payload_is_assertion_fed():
    repo = _FakeRepo()
    vector = _FakeVectorIndex()
    pipeline = KnowledgeIndexingPipeline(repo=repo, vector_index=vector, extractor=_FakeExtractor())
    asyncio.run(
        pipeline.index_training_content(
            kb_id=1,
            kb_uuid="kb-1",
            collection="c1",
            source_point_id="p1",
            sanitized_text="Péter dolgozik ProjektX-ben.",
            title="t",
        )
    )
    payload = vector.sentence_rows[0]["payload"]
    assert payload["entity_ids"]
    assert payload["assertion_ids"]
    assert payload["time_from"] is not None


def test_structural_chunk_payload_is_assertion_fed():
    repo = _FakeRepo()
    vector = _FakeVectorIndex()
    pipeline = KnowledgeIndexingPipeline(repo=repo, vector_index=vector, extractor=_FakeExtractor())
    asyncio.run(
        pipeline.index_training_content(
            kb_id=1,
            kb_uuid="kb-1",
            collection="c1",
            source_point_id="p1",
            sanitized_text="Péter dolgozik ProjektX-ben. Ez egy második mondat.",
            title="t",
        )
    )
    payload = vector.chunk_rows[0]["payload"]
    assert payload["entity_ids"]
    assert payload["assertion_ids"]
    assert payload["time_from"] is not None


def test_assertion_evidence_created_on_first_insert():
    repo = _FakeRepo()
    vector = _FakeVectorIndex()
    pipeline = KnowledgeIndexingPipeline(repo=repo, vector_index=vector, extractor=_FakeExtractor())
    asyncio.run(
        pipeline.index_training_content(
            kb_id=1,
            kb_uuid="kb-1",
            collection="c1",
            source_point_id="p1",
            sanitized_text="Péter dolgozik ProjektX-ben.",
            title="t",
        )
    )
    assert len(repo.evidences) == 1
    assert repo.evidences[0]["evidence_type"] == "PRIMARY"


class _FakeExtractorFingerprintMatch:
    async def extract(self, sanitized_text: str, title: str | None = None) -> dict:
        _ = (sanitized_text, title)
        return {
            "entities": [
                {"canonical_name": "Anna", "entity_type": "PERSON", "aliases": [], "confidence": 0.9},
            ],
            "assertions": [
                {
                    "subject": "Anna",
                    "predicate": "vezet",
                    "object": "csapatot",
                    "source_sentence_index": 0,
                    "time_from": "2024",
                    "time_to": "2024",
                    "place_key": "Debrecen",
                    "attributes": [],
                    "canonical_text": "Anna vezet csapatot",
                    "confidence": 0.8,
                },
                {
                    "subject": "Anna",
                    "predicate": "vezet",
                    "object": "csapatot",
                    "source_sentence_index": 1,
                    "time_from": "2024",
                    "time_to": "2024",
                    "place_key": "Debrecen",
                    "attributes": [],
                    "canonical_text": "Anna vezet csapatot",
                    "confidence": 0.8,
                },
            ],
        }


def test_assertion_evidence_added_on_fingerprint_match():
    repo = _FakeRepo()
    vector = _FakeVectorIndex()
    pipeline = KnowledgeIndexingPipeline(repo=repo, vector_index=vector, extractor=_FakeExtractorFingerprintMatch())
    asyncio.run(
        pipeline.index_training_content(
            kb_id=1,
            kb_uuid="kb-1",
            collection="c1",
            source_point_id="p1",
            sanitized_text="Anna vezet csapatot. Ugyanezt megerősíti a következő mondat is.",
            title="t",
        )
    )
    assert len(repo.assertions_by_fp) == 1
    assert len(repo.evidences) == 2
    assert repo.evidences[0]["sentence_id"] != repo.evidences[1]["sentence_id"]


class _FakeExtractorCandidateFallback:
    async def extract(self, sanitized_text: str, title: str | None = None) -> dict:
        _ = (sanitized_text, title)
        return {
            "extraction_confidence": 0.8,
            "entities": [
                {"canonical_name": "Anna", "entity_type": "PERSON", "aliases": [], "confidence": 0.9},
            ],
            "mentions": [],
            "assertions": [
                {
                    "subject": "Anna",
                    "predicate": "dolgozik",
                    "source_sentence_index": 0,
                    "canonical_text": "Anna dolgozik",
                    "confidence": 0.8,
                }
            ],
            "time_candidates": [
                {"source_sentence_index": 0, "time_from": "2024-01-01", "time_to": "2024-01-31"},
            ],
            "place_candidates": [
                {"source_sentence_index": 0, "canonical_name": "Budapest"},
            ],
        }


def test_time_and_place_fallback_from_candidates():
    repo = _FakeRepo()
    vector = _FakeVectorIndex()
    pipeline = KnowledgeIndexingPipeline(repo=repo, vector_index=vector, extractor=_FakeExtractorCandidateFallback())
    asyncio.run(
        pipeline.index_training_content(
            kb_id=1,
            kb_uuid="kb-1",
            collection="c1",
            source_point_id="p1",
            sanitized_text="Anna dolgozik.",
            title="t",
        )
    )
    assertion = next(iter(repo.assertions_by_fp.values()))
    assert assertion["time_from"] is not None
    assert assertion["time_to"] is not None
    assert assertion["place_key"] == "budapest"


class _FakeExtractorSourceTime:
    async def extract(self, sanitized_text: str, title: str | None = None) -> dict:
        _ = (sanitized_text, title)
        return {
            "entities": [{"canonical_name": "Júlia", "entity_type": "PERSON", "aliases": [], "confidence": 0.9}],
            "mentions": [],
            "assertions": [
                {
                    "subject": "Júlia",
                    "predicate": "vezet",
                    "source_sentence_index": 0,
                    "canonical_text": "Júlia vezet",
                    "source_time": "2024-02-03",
                    "confidence": 0.9,
                }
            ],
            "time_candidates": [],
            "place_candidates": [],
        }


def test_source_time_and_ingest_time_are_separated():
    repo = _FakeRepo()
    vector = _FakeVectorIndex()
    pipeline = KnowledgeIndexingPipeline(repo=repo, vector_index=vector, extractor=_FakeExtractorSourceTime())
    asyncio.run(
        pipeline.index_training_content(
            kb_id=1,
            kb_uuid="kb-1",
            collection="c1",
            source_point_id="p1",
            sanitized_text="Júlia vezet.",
            title="t",
        )
    )
    assertion = next(iter(repo.assertions_by_fp.values()))
    assert assertion.get("source_time") is not None
    assert assertion.get("ingest_time") is not None
    payload = vector.assertion_rows[0]["payload"]
    assert payload.get("source_time") is not None
    assert payload.get("ingest_time") is not None
