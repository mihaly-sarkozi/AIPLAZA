"""Enrichment adapter: JSON parzolás, clamping, limitek."""
from __future__ import annotations

import pytest

from apps.kb.kb_understanding.adapters.LlmEnrichmentAdapter import LlmEnrichmentAdapter

pytestmark = pytest.mark.unit


class _FakeLlm:
    def __init__(self, payload) -> None:
        self._payload = payload

    def complete_json(self, *, system: str, user: str, max_tokens: int = 1500):
        return self._payload


def test_parses_full_enrichment_payload():
    payload = {
        "summary": "Rövid összefoglaló.",
        "keywords": ["jelszó", "biztonság"],
        "topics": ["fiókkezelés"],
        "content_type": "FAQ",
        "language": "HU",
        "difficulty": "basic",
        "importance": 0.8,
        "possible_questions": ["Hogyan módosítok jelszót?"],
        "confidence": 0.95,
    }
    dto = LlmEnrichmentAdapter(_FakeLlm(payload)).enrich_chunk("chunk_1", "szöveg")
    assert dto.chunk_id == "chunk_1"
    assert dto.summary == "Rövid összefoglaló."
    assert dto.keywords == ("jelszó", "biztonság")
    assert dto.topics == ("fiókkezelés",)
    assert dto.content_type == "faq"
    assert dto.language == "hu"
    assert dto.difficulty == "basic"
    assert dto.importance == 0.8
    assert dto.confidence == 0.95


def test_invalid_values_are_clamped_or_dropped():
    payload = {
        "summary": "",
        "keywords": "nem lista",
        "topics": None,
        "difficulty": "extreme",
        "importance": 7,
        "confidence": -3,
    }
    dto = LlmEnrichmentAdapter(_FakeLlm(payload)).enrich_chunk("chunk_1", "szöveg")
    assert dto.keywords == ()
    assert dto.topics == ()
    assert dto.difficulty is None
    assert dto.importance == 1.0
    assert dto.confidence == 0.0


def test_list_limits_enforced():
    payload = {
        "summary": "x",
        "keywords": [f"k{i}" for i in range(20)],
        "topics": [f"t{i}" for i in range(20)],
        "possible_questions": [f"q{i}" for i in range(20)],
    }
    dto = LlmEnrichmentAdapter(_FakeLlm(payload)).enrich_chunk("chunk_1", "szöveg")
    assert len(dto.keywords) == 8
    assert len(dto.topics) == 4
    assert len(dto.possible_questions) == 5


def test_non_dict_payload_yields_empty_enrichment():
    dto = LlmEnrichmentAdapter(_FakeLlm(["lista"])).enrich_chunk("chunk_1", "szöveg")
    assert dto.summary == ""
    assert dto.confidence == 0.0
