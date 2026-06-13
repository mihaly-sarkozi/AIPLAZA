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


@pytest.mark.parametrize(
    ("text", "language_code", "expected_fragment"),
    [
        ("La Empresa Demo S.L. opera en Madrid.", "es", "Empresa Demo S.L."),
        ("Grupo Norte S.A. reportó resultados.", "es", "Grupo Norte S.A."),
        ("Acme Solutions Inc. signed the deal.", "en", "Acme Solutions Inc."),
        ("Global Trade Ltd. opened a branch.", "en", "Global Trade Ltd."),
        ("OpenAI, LLC policy applies.", "en", "OpenAI, LLC"),
    ],
)
def test_legal_form_recognizer_handles_dotted_suffixes(text, language_code, expected_fragment):
    recognizer = LegalFormCompanyRecognizer()
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text=text,
            chunk_type="paragraph",
            order_index=0,
            language_code=language_code,
        )
    ]
    context = DiscoveryContext(
        tenant_slug="tenant",
        knowledge_base_id="kb1",
        training_item_id="item1",
    )
    result = recognizer.recognize(chunks, context)
    assert any(item.name == expected_fragment for item in result)


def test_systems_gazetteer_loads_tenant_and_kb_overlays():
    from apps.kb.kb_discovery.gazetteers.SystemsGazetteer import SystemsGazetteer

    systems = SystemsGazetteer().systems_for(
        tenant_slug="demo",
        knowledge_base_id="example-kb",
    )
    assert "HubSpot" in systems
    assert "Belső CRM" in systems
    assert "Projekt Atlas API" in systems


def test_person_directory_provider_loads_tenant_file():
    from apps.kb.kb_discovery.persons.PersonDirectoryProvider import PersonDirectoryProvider

    directory = PersonDirectoryProvider().load(
        tenant_slug="demo",
        knowledge_base_id="missing-kb",
    )
    names = {entry["name"] for entry in directory}
    assert "Mihály Sárközi" in names


def test_person_alias_entry_import_has_no_circular_dependency():
    import importlib

    importlib.import_module("apps.kb.kb_discovery.persons.PersonAliasRecognizer")
    importlib.import_module("apps.kb.kb_discovery.persons.PersonDisambiguator")
