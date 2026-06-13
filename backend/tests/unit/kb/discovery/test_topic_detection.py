from __future__ import annotations

import pytest

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.topics.TopicDetectionService import TopicDetectionService

pytestmark = pytest.mark.unit


def test_hubspot_maps_to_sales_topic():
    service = TopicDetectionService()
    chunk = DiscoveryChunkDto(
        chunk_id="c1",
        text="HubSpot CRM bevezetése folyamatban.",
        chunk_type="paragraph",
        order_index=0,
        language_code="hu",
    )
    topics = service.detect_for_chunk(
        chunk,
        language_code="hu",
        keyword_terms=["hubspot", "crm"],
    )
    assert any(t.topic_key == "sales" for t in topics)
