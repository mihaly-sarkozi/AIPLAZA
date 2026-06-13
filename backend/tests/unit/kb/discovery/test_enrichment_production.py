from __future__ import annotations

import pytest

from apps.kb.kb_discovery.content_types.ContentTypeDetectionService import ContentTypeDetectionService
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.enrichment.LocalKnowledgeEnrichmentService import LocalKnowledgeEnrichmentService
from apps.kb.kb_discovery.repository.EnrichmentRepository import bundle_to_indexing_payload

pytestmark = pytest.mark.unit


class _Repo:
    def __init__(self) -> None:
        self.rows = []

    def replace_for_job(self, job_id, rows):
        self.rows = rows


class _MentionRepo:
    def list_by_job_grouped_by_chunk(self, job_id):
        return {}


def _ctx():
    return DiscoveryJobContext(
        job_id="disc_job_1",
        understanding_job_id="und_job_1",
        training_item_id="item1",
        training_batch_id="batch1",
        knowledge_base_id="kb1",
        tenant_slug="tenant",
        created_by=1,
        source_type="text",
        title="t",
        language_code="hu",
        language_confidence=0.8,
    )


def test_content_type_detection_prefers_process_for_numbered_steps():
    service = ContentTypeDetectionService()
    chunk = DiscoveryChunkDto(
        chunk_id="c1",
        text="1. Nyissa meg a HubSpotot.\n2. Indítsa el a szinkront.",
        chunk_type="paragraph",
        order_index=0,
    )
    result = service.detect_for_chunk(chunk)
    assert result.content_type == "process"
    assert result.confidence >= 0.7


def test_enrichment_profile_does_not_store_full_keyword_lists():
    enrichment_repo = _Repo()
    keyword_repo = _Repo()
    topic_repo = _Repo()
    service = LocalKnowledgeEnrichmentService(
        enrichment_repo,
        keyword_repo,
        topic_repo,
        _MentionRepo(),
    )
    chunk = DiscoveryChunkDto(
        chunk_id="c1",
        text="Az ügyfél számlázása HubSpot integrációval történik.",
        chunk_type="paragraph",
        order_index=0,
        language_code="hu",
        language_confidence=0.9,
    )
    result = service.run(_ctx(), [chunk])
    enrichment = result.enrichments[0]
    assert hasattr(enrichment, "metadata")
    assert "keyword_count" in enrichment.metadata
    assert "top_keywords" in enrichment.metadata
    assert not hasattr(enrichment, "keywords")
    assert enrichment.preview_text
    assert enrichment.profile_confidence > 0


def test_bundle_to_indexing_payload_shape():
    class _Enrichment:
        language_code = "hu"
        content_type = "process"
        profile_confidence = 0.8

    class _Keyword:
        normalized_term = "hubspot"

    class _Topic:
        topic_key = "sales"

    payload = bundle_to_indexing_payload(
        type("Bundle", (), {
            "enrichment": _Enrichment(),
            "keywords": (_Keyword(),),
            "topics": (_Topic(),),
        })()
    )
    assert payload["language_code"] == "hu"
    assert payload["keywords"] == ["hubspot"]
    assert payload["topics"] == ["sales"]
