from __future__ import annotations

import pytest

from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.enums.EntityType import EntityType
from apps.kb.kb_discovery.persons.GivenNameRecognizer import GivenNameRecognizer
from apps.kb.kb_discovery.persons.PersonConfidenceScorer import (
    GIVEN_NAME_CANDIDATE_CONFIDENCE,
    PERSON_ENTITY_MIN_CONFIDENCE,
)

pytestmark = pytest.mark.unit


def test_given_name_is_low_confidence_candidate_only():
    recognizer = GivenNameRecognizer()
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="Mihály dolgozott a projekten.",
            chunk_type="paragraph",
            order_index=0,
            language_code="hu",
        )
    ]
    context = DiscoveryContext(
        tenant_slug="tenant",
        knowledge_base_id="kb1",
        training_item_id="item1",
        person_directory=[],
    )
    result = recognizer.recognize(chunks, context)
    assert len(result) == 1
    assert result[0].entity_type == EntityType.PERSON
    assert result[0].confidence == GIVEN_NAME_CANDIDATE_CONFIDENCE
    assert result[0].confidence < PERSON_ENTITY_MIN_CONFIDENCE
