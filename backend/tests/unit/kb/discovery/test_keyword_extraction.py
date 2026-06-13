from __future__ import annotations

import pytest

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.keywords.KeywordExtractionService import KeywordExtractionService

pytestmark = pytest.mark.unit


class _FakeKeywordRepo:
    def __init__(self) -> None:
        self.saved = []

    def replace_for_job(self, job_id, keywords):
        self.saved = keywords
        return len(keywords)


def test_keyword_extraction_finds_terms():
    service = KeywordExtractionService(_FakeKeywordRepo())
    ctx = DiscoveryJobContext(
        job_id="disc_job_1",
        understanding_job_id="und_job_1",
        training_item_id="item1",
        training_batch_id="batch1",
        knowledge_base_id="kb1",
        tenant_slug="tenant",
        created_by=1,
        source_type="text",
        title="t",
    )
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="Az ACME Kft. HubSpotot és irodát említ.",
            chunk_type="paragraph",
            order_index=0,
        )
    ]
    keywords = service.run(ctx, chunks)
    terms = {k.term.lower() for k in keywords}
    assert "acme" in terms or any("acme" in t.lower() for t in terms)
    assert any("hubspot" in t.lower() for t in terms) or "hubspot" in terms
    assert any("irod" in t.lower() for t in terms)
