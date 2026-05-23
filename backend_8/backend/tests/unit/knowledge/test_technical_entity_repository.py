from __future__ import annotations

from uuid import uuid4

import pytest

from apps.knowledge.domain.technical_entity import TechnicalEntity
from apps.knowledge.repository.technical_entity_repository import TechnicalEntityRepository


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_runtime_technical_entity_repository_save_list_delete() -> None:
    run_id = uuid4()
    source_id = uuid4()
    entity = TechnicalEntity(
        run_id=run_id,
        source_id=source_id,
        canonical_name="Search module",
        entity_type="module",
        normalized_key="search module",
    )
    repo = TechnicalEntityRepository()

    assert repo.save(entity) == entity
    assert repo.get(entity.technical_entity_id) == entity
    assert repo.list_by_run(run_id) == [entity]
    assert repo.list_by_source(source_id) == [entity]
    assert repo.delete_by_run(run_id) == 1
    assert repo.get(entity.technical_entity_id) is None


def test_runtime_technical_entity_repository_delete_by_source() -> None:
    source_id = uuid4()
    repo = TechnicalEntityRepository()
    repo.save_many(
        [
            TechnicalEntity(source_id=source_id, canonical_name="A"),
            TechnicalEntity(source_id=source_id, canonical_name="B"),
        ]
    )

    assert repo.delete_by_source(source_id) == 2
    assert repo.list_by_source(source_id) == []
