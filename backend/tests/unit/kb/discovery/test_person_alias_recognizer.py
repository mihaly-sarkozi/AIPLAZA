from __future__ import annotations

import pytest

from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.enums.EntityType import EntityType
from apps.kb.kb_discovery.persons.PersonAliasRecognizer import PersonAliasRecognizer

pytestmark = pytest.mark.unit


def test_misi_not_person_without_alias():
    recognizer = PersonAliasRecognizer()
    chunks = [DiscoveryChunkDto(chunk_id="c1", text="Misi okos", chunk_type="paragraph", order_index=0)]
    context = DiscoveryContext(
        tenant_slug="tenant",
        knowledge_base_id="kb1",
        training_item_id="item1",
        person_directory=[],
    )
    result = recognizer.recognize(chunks, context)
    assert result == []


def test_misi_person_with_alias():
    recognizer = PersonAliasRecognizer()
    chunks = [DiscoveryChunkDto(chunk_id="c1", text="Misi okos", chunk_type="paragraph", order_index=0)]
    context = DiscoveryContext(
        tenant_slug="tenant",
        knowledge_base_id="kb1",
        training_item_id="item1",
        person_directory=[{"name": "Mihály", "aliases": ["Misi"]}],
    )
    result = recognizer.recognize(chunks, context)
    assert len(result) == 1
    assert result[0].entity_type == EntityType.PERSON
    assert result[0].name == "Misi"


def test_person_alias_matches_accent_variants():
    recognizer = PersonAliasRecognizer()
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="Mihaly Sarkozi dolgozott a projekten.",
            chunk_type="paragraph",
            order_index=0,
        )
    ]
    context = DiscoveryContext(
        tenant_slug="tenant",
        knowledge_base_id="kb1",
        training_item_id="item1",
        person_directory=[{"name": "Mihály Sárközi", "aliases": ["Mihály", "Misi"]}],
    )
    result = recognizer.recognize(chunks, context)
    matched_names = {item.name for item in result}
    assert "Mihaly" in matched_names
