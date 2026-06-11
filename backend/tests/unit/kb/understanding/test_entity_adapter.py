"""Entity adapter: LLM JSON parzolás (fake klienssel), regex-kiegészítés, merge."""
from __future__ import annotations

import json

import pytest

from apps.kb.kb_understanding.adapters.EntityExtractorAdapter import EntityExtractorAdapter
from apps.kb.kb_understanding.adapters.LlmCompletionAdapter import LlmCompletionAdapter
from apps.kb.kb_understanding.enums.EntityType import EntityType
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError

pytestmark = pytest.mark.unit


class _FakeLlm:
    def __init__(self, payload) -> None:
        self._payload = payload
        self.calls: list[dict] = []

    def complete_json(self, *, system: str, user: str, max_tokens: int = 1500):
        self.calls.append({"system": system, "user": user})
        return self._payload


def test_parses_llm_entities_with_alias_and_confidence():
    payload = {
        "entities": [
            {
                "type": "company",
                "name": "ACME Kft.",
                "aliases": ["ACME"],
                "confidence": 0.9,
                "chunk_ids": ["chunk_1"],
            }
        ]
    }
    adapter = EntityExtractorAdapter(_FakeLlm(payload))
    entities = adapter.extract_entities([("chunk_1", "Az ACME Kft. szállítja a terméket.")])
    company = next(entity for entity in entities if entity.entity_type == EntityType.COMPANY)
    assert company.name == "ACME Kft."
    assert company.aliases == ("ACME",)
    assert company.confidence == 0.9
    assert company.chunk_ids == ("chunk_1",)


def test_unknown_type_maps_to_other_and_invalid_chunk_ids_dropped():
    payload = {
        "entities": [
            {"type": "alien", "name": "Valami", "confidence": 0.7, "chunk_ids": ["nem_letezo"]}
        ]
    }
    adapter = EntityExtractorAdapter(_FakeLlm(payload))
    entities = adapter.extract_entities([("chunk_1", "Valami szöveg.")])
    other = next(entity for entity in entities if entity.name == "Valami")
    assert other.entity_type == EntityType.OTHER
    assert other.chunk_ids == ()


def test_regex_augmentation_finds_date_and_ticket():
    adapter = EntityExtractorAdapter(_FakeLlm({"entities": []}))
    entities = adapter.extract_entities(
        [("chunk_1", "Határidő: 2026.06.11. A hibajegy: PROJ-1234.")]
    )
    types = {entity.entity_type for entity in entities}
    assert EntityType.DATE in types
    assert EntityType.TICKET_ID in types
    date_entity = next(entity for entity in entities if entity.entity_type == EntityType.DATE)
    assert date_entity.confidence == 1.0
    assert date_entity.chunk_ids == ("chunk_1",)


def test_duplicate_entities_are_merged():
    payload = {
        "entities": [
            {"type": "person", "name": "Kiss Anna", "confidence": 0.6, "chunk_ids": ["chunk_1"]},
            {"type": "person", "name": "kiss anna", "confidence": 0.9, "chunk_ids": ["chunk_2"]},
        ]
    }
    adapter = EntityExtractorAdapter(_FakeLlm(payload))
    entities = adapter.extract_entities([("chunk_1", "a"), ("chunk_2", "b")])
    persons = [entity for entity in entities if entity.entity_type == EntityType.PERSON]
    assert len(persons) == 1
    assert persons[0].confidence == 0.9
    assert set(persons[0].chunk_ids) == {"chunk_1", "chunk_2"}


def test_llm_json_parse_handles_code_fence():
    parsed = LlmCompletionAdapter._parse_json('```json\n{"entities": []}\n```')
    assert parsed == {"entities": []}


def test_llm_json_parse_extracts_embedded_object():
    content = "A válasz: " + json.dumps({"summary": "ok"}) + " — kész."
    assert LlmCompletionAdapter._parse_json(content) == {"summary": "ok"}


def test_llm_json_parse_failure_raises_retryable():
    with pytest.raises(UnderstandingProcessingError) as excinfo:
        LlmCompletionAdapter._parse_json("ez nem json")
    assert excinfo.value.code == UnderstandingErrorCode.LLM_UNAVAILABLE.value
    assert excinfo.value.retryable is True
