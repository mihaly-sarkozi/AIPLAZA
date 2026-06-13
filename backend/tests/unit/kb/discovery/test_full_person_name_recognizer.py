from __future__ import annotations

import pytest

from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.enums.EntityType import EntityType
from apps.kb.kb_discovery.persons.FullPersonNameRecognizer import FullPersonNameRecognizer
from apps.kb.kb_discovery.persons.PersonConfidenceScorer import (
    FULL_NAME_BASE_CONFIDENCE,
    GIVEN_NAME_CANDIDATE_CONFIDENCE,
    PERSON_ENTITY_MIN_CONFIDENCE,
)
from apps.kb.kb_discovery.persons.PersonRecognitionService import PersonRecognitionService
from apps.kb.kb_discovery.repository.EntityRepository import EntityMentionRepository, EntityRepository

pytestmark = pytest.mark.unit


class _FakeRepo:
    def replace_for_job(self, *_args, **_kwargs):
        return 0

    def replace_for_document(self, *_args, **_kwargs):
        return 0


def _context(directory=None):
    return DiscoveryContext(
        tenant_slug="tenant",
        knowledge_base_id="kb1",
        training_item_id="item1",
        person_directory=directory or [],
    )


def test_full_person_name_recognizer_finds_hungarian_name():
    recognizer = FullPersonNameRecognizer()
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="Mihály Sárközi vezeti a projektet.",
            chunk_type="paragraph",
            order_index=0,
            language_code="hu",
        )
    ]
    result = recognizer.recognize(chunks, _context())
    assert len(result) == 1
    assert "Mihály" in result[0].name
    assert result[0].confidence == FULL_NAME_BASE_CONFIDENCE
    assert result[0].confidence >= PERSON_ENTITY_MIN_CONFIDENCE


def test_full_person_name_recognizer_finds_reversed_hungarian_order():
    recognizer = FullPersonNameRecognizer()
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="Sárközi Mihály jelentést készített.",
            chunk_type="paragraph",
            order_index=0,
            language_code="hu",
        )
    ]
    result = recognizer.recognize(chunks, _context())
    assert len(result) == 1
    assert result[0].name == "Mihály Sárközi"


def test_full_person_name_recognizer_boosts_directory_hit():
    recognizer = FullPersonNameRecognizer()
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="Mihály Sárközi aláírta.",
            chunk_type="paragraph",
            order_index=0,
            language_code="hu",
        )
    ]
    directory = [{"name": "Mihály Sárközi", "aliases": ["Mihály", "Misi"]}]
    result = recognizer.recognize(chunks, _context(directory))
    assert result[0].confidence > FULL_NAME_BASE_CONFIDENCE


def test_given_name_alone_not_persisted_by_person_service():
    service = PersonRecognitionService(_FakeRepo(), _FakeRepo())
    from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext

    ctx = DiscoveryJobContext(
        job_id="job1",
        understanding_job_id="und1",
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
            text="Mihály dolgozott a projekten.",
            chunk_type="paragraph",
            order_index=0,
            language_code="hu",
        )
    ]
    entities, mentions = service.run(ctx, chunks)
    assert entities == []
    assert mentions == []


def test_person_service_keeps_single_mention_for_full_name_over_aliases():
    from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext

    service = PersonRecognitionService(_FakeRepo(), _FakeRepo())
    ctx = DiscoveryJobContext(
        job_id="job1",
        understanding_job_id="und1",
        training_item_id="item1",
        training_batch_id="batch1",
        knowledge_base_id="example-kb",
        tenant_slug="demo",
        created_by=1,
        source_type="text",
        title="t",
    )
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="Carlos García aláírta a szerződést.",
            chunk_type="paragraph",
            order_index=0,
            language_code="es",
        )
    ]
    _entities, mentions = service.run(ctx, chunks)
    assert len(mentions) == 1
    assert mentions[0].raw_text == "Carlos García"


def test_full_name_persisted_by_person_service():
    from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext

    service = PersonRecognitionService(_FakeRepo(), _FakeRepo())
    ctx = DiscoveryJobContext(
        job_id="job1",
        understanding_job_id="und1",
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
            text="Mihály Sárközi aláírta a dokumentumot.",
            chunk_type="paragraph",
            order_index=0,
            language_code="hu",
        )
    ]
    entities, mentions = service.run(ctx, chunks)
    assert len(entities) == 1
    assert entities[0].entity_type == EntityType.PERSON
    assert len(mentions) == 1
    assert mentions[0].recognizer_name == "full_person_name"
    assert mentions[0].confidence >= PERSON_ENTITY_MIN_CONFIDENCE
    assert GIVEN_NAME_CANDIDATE_CONFIDENCE < PERSON_ENTITY_MIN_CONFIDENCE
