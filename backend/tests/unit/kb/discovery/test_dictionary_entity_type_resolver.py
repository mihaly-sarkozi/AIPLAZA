from __future__ import annotations

import pytest

from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.entities.DictionaryEntityRecognizer import DictionaryEntityRecognizer
from apps.kb.kb_discovery.entities.entity_type_resolver import resolve_entity_type
from apps.kb.kb_discovery.enums.EntityType import EntityType

pytestmark = pytest.mark.unit


def test_resolve_entity_type_falls_back_to_other():
    context = DiscoveryContext(
        tenant_slug="tenant",
        knowledge_base_id="kb1",
        training_item_id="item1",
    )
    entity_type = resolve_entity_type("organization", entry_name="ACME", context=context)
    assert entity_type == EntityType.OTHER
    assert len(context.dictionary_warnings) == 1


def test_dictionary_recognizer_skips_invalid_type_without_crash():
    recognizer = DictionaryEntityRecognizer()
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="ACME szervezet működik.",
            chunk_type="paragraph",
            order_index=0,
        )
    ]
    context = DiscoveryContext(
        tenant_slug="tenant",
        knowledge_base_id="kb1",
        training_item_id="item1",
        entity_dictionary=[{"name": "ACME", "type": "organization", "confidence": 0.8}],
    )
    result = recognizer.recognize(chunks, context)
    assert len(result) == 1
    assert result[0].entity_type == EntityType.OTHER
    assert len(context.dictionary_warnings) == 1
