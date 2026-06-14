from __future__ import annotations

import pytest

from apps.kb.kb_discovery.repository.DiscoveryBundleRepository import DiscoveryBundleRepository

pytestmark = pytest.mark.unit


class _EnrichmentRepo:
    def get_enrichment_bundle_for_chunks(self, job_id, chunk_ids):
        class _Bundle:
            enrichment = type("E", (), {"language_code": "hu"})()
            keywords = ()
            topics = ()

        return {chunk_id: _Bundle() for chunk_id in chunk_ids}


class _EntityRepo:
    def list_for_chunks(self, training_item_id, chunk_ids):
        return []


class _MentionRepo:
    def list_by_job_grouped_by_chunk(self, job_id):
        return {"c1": [type("M", (), {"chunk_id": "c1"})()]}


class _TemporalRepo:
    def list_for_chunks(self, job_id, chunk_ids):
        return [type("T", (), {"chunk_id": "c1"})()]


class _SpatialRepo:
    def list_for_chunks(self, job_id, chunk_ids):
        return []


class _ProcessRepo:
    def list_for_chunks(self, job_id, chunk_ids):
        return []


class _RelationshipRepo:
    def list_for_chunks(self, job_id, chunk_ids):
        return [
            type(
                "R",
                (),
                {
                    "id": "r1",
                    "to_type": "chunk",
                    "to_id": "c1",
                    "from_type": "entity",
                    "from_id": "company:acme",
                    "evidence_chunk_ids": ["c1"],
                },
            )()
        ]


class _ScoreRepo:
    def get_for_chunks(self, job_id, chunk_ids):
        return {"c1": type("S", (), {"chunk_id": "c1", "knowledge_score": 0.8})()}


def test_discovery_bundle_returns_full_chunk_payload():
    repo = DiscoveryBundleRepository(
        _EnrichmentRepo(),
        _EntityRepo(),
        _MentionRepo(),
        _TemporalRepo(),
        _SpatialRepo(),
        _ProcessRepo(),
        _RelationshipRepo(),
        _ScoreRepo(),
    )
    bundle = repo.get_bundle_for_chunks("job1", "item1", ["c1"])["c1"]
    assert bundle.language_code == "hu"
    assert len(bundle.entity_mentions) == 1
    assert len(bundle.temporal_mentions) == 1
    assert len(bundle.relationships) == 1
    assert bundle.score is not None
