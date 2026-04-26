from __future__ import annotations

from uuid import UUID

from apps.knowledge.domain.technical_entity import TechnicalEntity


def _parse_uuid(value: str | UUID) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


class TechnicalEntityRepository:
    """Runtime-only TechnicalEntity repository.

    TODO: ha a Technical Entity perzisztens termékfelület lesz, kapjon saját ORM modellt,
    tenant hook táblát és DB-backed repository implementációt. Jelenleg nincs migration:
    a builder kimenete runtime / trace rétegben tartható.
    """

    def __init__(self) -> None:
        self._by_id: dict[UUID, TechnicalEntity] = {}

    def save(self, entity: TechnicalEntity) -> TechnicalEntity:
        self._by_id[entity.technical_entity_id] = entity
        return entity

    def save_many(self, entities: list[TechnicalEntity]) -> list[TechnicalEntity]:
        for entity in entities:
            self.save(entity)
        return list(entities)

    def get(self, technical_entity_id: str | UUID) -> TechnicalEntity | None:
        return self._by_id.get(_parse_uuid(technical_entity_id))

    def list_by_run(self, run_id: str | UUID) -> list[TechnicalEntity]:
        rid = _parse_uuid(run_id)
        return sorted(
            [item for item in self._by_id.values() if item.run_id == rid],
            key=lambda item: item.created_at,
        )

    def list_by_source(self, source_id: str | UUID) -> list[TechnicalEntity]:
        sid = _parse_uuid(source_id)
        return sorted(
            [item for item in self._by_id.values() if item.source_id == sid],
            key=lambda item: item.created_at,
        )

    def delete_by_run(self, run_id: str | UUID) -> int:
        rid = _parse_uuid(run_id)
        ids = [item.technical_entity_id for item in self._by_id.values() if item.run_id == rid]
        for entity_id in ids:
            self._by_id.pop(entity_id, None)
        return len(ids)

    def delete_by_source(self, source_id: str | UUID) -> int:
        sid = _parse_uuid(source_id)
        ids = [item.technical_entity_id for item in self._by_id.values() if item.source_id == sid]
        for entity_id in ids:
            self._by_id.pop(entity_id, None)
        return len(ids)


__all__ = ["TechnicalEntityRepository"]
