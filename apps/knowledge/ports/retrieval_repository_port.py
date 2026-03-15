from __future__ import annotations

from abc import ABC, abstractmethod


class RetrievalRepositoryPort(ABC):
    @abstractmethod
    def delete_derived_records_by_source_point_id(self, kb_id: int, source_point_id: str) -> int:
        """Derived rekordok törlése source_point alapján."""
        ...

    @abstractmethod
    def get_allowed_kb_ids_for_user(self, user_id: int) -> list[int]:
        """Felhasználó által használható KB id-k."""
        ...
