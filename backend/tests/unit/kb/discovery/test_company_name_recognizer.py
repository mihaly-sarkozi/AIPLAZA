from __future__ import annotations

import pytest

from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.entities.CompanyNameRecognizer import CompanyNameRecognizer
from apps.kb.kb_discovery.enums.EntityType import EntityType

pytestmark = pytest.mark.unit


def test_acme_kft_company():
    recognizer = CompanyNameRecognizer()
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="Az ACME Kft. szerződést kötött.",
            chunk_type="paragraph",
            order_index=0,
        )
    ]
    context = DiscoveryContext(tenant_slug="t", knowledge_base_id="kb", training_item_id="item")
    result = recognizer.recognize(chunks, context)
    assert len(result) == 1
    assert result[0].entity_type == EntityType.COMPANY
    assert "ACME Kft." in result[0].name
