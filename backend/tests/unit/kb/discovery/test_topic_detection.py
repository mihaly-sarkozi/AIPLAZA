from __future__ import annotations

import pytest

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.topics.TopicDetectionService import TopicDetectionService

pytestmark = pytest.mark.unit


class _FakeTopicRepo:
    def replace_for_job(self, job_id, topics):
        return len(topics)


def test_hubspot_maps_to_sales_topic():
    service = TopicDetectionService(_FakeTopicRepo())
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
            text="HubSpot CRM bevezetése folyamatban.",
            chunk_type="paragraph",
            order_index=0,
        )
    ]
    topics = service.run(ctx, chunks)
    assert any(t.topic_key == "sales" for t in topics)
