from __future__ import annotations

import pytest

from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.entities.DictionaryEntityRecognizer import SystemNameRecognizer
from apps.kb.kb_discovery.enums.EntityType import EntityType

pytestmark = pytest.mark.unit


def test_hubspot_system_entity():
    recognizer = SystemNameRecognizer()
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="A HubSpot használata kötelező.",
            chunk_type="paragraph",
            order_index=0,
        )
    ]
    context = DiscoveryContext(tenant_slug="t", knowledge_base_id="kb", training_item_id="item")
    result = recognizer.recognize(chunks, context)
    assert any(r.entity_type == EntityType.SYSTEM and "hubspot" in r.normalized_name for r in result)
