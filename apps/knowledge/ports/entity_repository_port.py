from __future__ import annotations

from abc import ABC, abstractmethod


class EntityRepositoryPort(ABC):
    @abstractmethod
    def upsert_entity(self, kb_id: int, payload: dict) -> dict:
        """Entitás upsert canonical név szerint."""
        ...
