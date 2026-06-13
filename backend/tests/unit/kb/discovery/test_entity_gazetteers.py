from __future__ import annotations

import pytest

from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.entities.DictionaryEntityRecognizer import DictionaryEntityRecognizer
from apps.kb.kb_discovery.entities.LegalFormCompanyRecognizer import LegalFormCompanyRecognizer
from apps.kb.kb_discovery.enums.EntityType import EntityType

pytestmark = pytest.mark.unit


def _context(entries):
    return DiscoveryContext(
        tenant_slug="tenant",
        knowledge_base_id="kb1",
        training_item_id="item1",
        entity_dictionary=entries,
    )


def test_dictionary_recognizer_finds_ai_plaza():
    recognizer = DictionaryEntityRecognizer()
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="Az AI Plaza modulban kezeljük a tanítást.",
            chunk_type="paragraph",
            order_index=0,
        )
    ]
    result = recognizer.recognize(
        chunks,
        _context([{"name": "AI Plaza", "type": "product", "confidence": 0.9}]),
    )
    assert len(result) == 1
    assert result[0].entity_type == EntityType.PRODUCT


def test_legal_form_recognizer_finds_hungarian_company():
    recognizer = LegalFormCompanyRecognizer()
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="A Zalka 2000 Kft. Budapesten működik.",
            chunk_type="paragraph",
            order_index=0,
            language_code="hu",
        )
    ]
    context = DiscoveryContext(
        tenant_slug="tenant",
        knowledge_base_id="kb1",
        training_item_id="item1",
    )
    result = recognizer.recognize(chunks, context)
    assert any("Zalka 2000 Kft." in item.name for item in result)
    assert all(item.entity_type == EntityType.COMPANY for item in result)
