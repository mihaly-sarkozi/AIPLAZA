from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from apps.knowledge.models.pii_mapping_orm import KnowledgePiiMappingORM
from apps.knowledge.repositories.pii_mapping_repository import KnowledgePiiMappingRepository

pytestmark = pytest.mark.unit


@pytest.mark.release_acceptance
def test_encryption_at_rest() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    KnowledgePiiMappingORM.__table__.create(engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    repo = KnowledgePiiMappingRepository(SessionFactory)
    token = repo.resolve_or_create_token(
        corpus_uuid="kb-1",
        entity_type="name",
        original_value="Kovács Anna",
    )
    assert token == "[szemely_1]"

    with SessionFactory() as session:
        row = session.execute(
            select(KnowledgePiiMappingORM).where(
                KnowledgePiiMappingORM.corpus_uuid == "kb-1",
                KnowledgePiiMappingORM.token == "[szemely_1]",
            )
        ).scalar_one()

    assert str(row.encrypted_value or "") != "Kovács Anna"
    assert str(row.encrypted_value or "").startswith("enc::")


@pytest.mark.release_acceptance
def test_entity_type_with_accents_gets_ai_friendly_token_label() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    KnowledgePiiMappingORM.__table__.create(engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    repo = KnowledgePiiMappingRepository(SessionFactory)
    token = repo.resolve_or_create_token(
        corpus_uuid="kb-1",
        entity_type="személyi azonosító",
        original_value="AU321654",
    )

    assert token == "[szemelyi_azonosito_1]"
