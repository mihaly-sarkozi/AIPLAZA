from __future__ import annotations

import pytest

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.keywords.KeywordExtractionService import KeywordExtractionService

pytestmark = pytest.mark.unit


def test_keyword_extraction_finds_terms():
    service = KeywordExtractionService()
    chunk = DiscoveryChunkDto(
        chunk_id="c1",
        text="Az ACME Kft. HubSpotot és irodát említ.",
        chunk_type="paragraph",
        order_index=0,
        language_code="hu",
    )
    keywords = service.extract_for_chunk(chunk, language_code="hu")
    terms = {k.normalized_term.lower() for k in keywords}
    assert "acme" in terms or any("acme" in t for t in terms)
    assert any("hubspot" in t for t in terms) or "hubspot" in terms
    assert keywords[0].source
    assert keywords[0].extractor_version


def test_keyword_extraction_supports_phrases():
    service = KeywordExtractionService()
    chunk = DiscoveryChunkDto(
        chunk_id="c1",
        text="Az ügyfél onboarding folyamat HubSpot integrációval indul.",
        chunk_type="paragraph",
        order_index=0,
        language_code="hu",
    )
    keywords = service.extract_for_chunk(chunk, language_code="hu")
    joined = " ".join(item.term.casefold() for item in keywords)
    assert "ügyfél onboarding" in joined or "hubspot" in joined
