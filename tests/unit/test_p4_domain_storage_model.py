from __future__ import annotations

import pytest

from apps.knowledge.domain.assertion import Assertion
from apps.knowledge.domain.block import Block
from apps.knowledge.domain.document import Document
from apps.knowledge.domain.mention import Mention
from apps.knowledge.infrastructure.db.models import KbAssertionRelationORM, KbPlaceORM

pytestmark = pytest.mark.unit


def test_domain_has_document_and_block_objects():
    doc = Document(kb_id=1, source_point_id="p1", title="T", sanitized_content="safe")
    blk = Block(source_point_id="p1", block_order=0, text="safe")
    assert doc.source_point_id == blk.source_point_id


def test_mention_is_distinct_from_entity_layer():
    mention = Mention(sentence_id=1, surface_form="Péter", mention_type="name")
    assert mention.resolved_entity_id is None


def test_assertion_time_semantics_are_separate():
    a = Assertion(
        kb_id=1,
        source_point_id="p1",
        predicate="dolgozik",
        canonical_text="Péter dolgozik",
        assertion_fingerprint="fp",
    )
    assert a.time_from is None and a.time_to is None
    assert a.source_time is None and a.ingest_time is None


def test_models_include_place_and_relation_confidence_columns():
    assert hasattr(KbPlaceORM, "place_type")
    assert hasattr(KbPlaceORM, "country_code")
    assert hasattr(KbAssertionRelationORM, "relation_confidence")
