from __future__ import annotations

from abc import ABC, abstractmethod


class AssertionRepositoryPort(ABC):
    @abstractmethod
    def upsert_assertion(self, kb_id: int, payload: dict) -> dict:
        """Assertion upsert fingerprint alapján."""
        ...

    @abstractmethod
    def list_assertions_by_source_point_id(self, kb_id: int, source_point_id: str) -> list[dict]:
        """Assertion lista source_point szerint."""
        ...

    @abstractmethod
    def search_candidate_assertions(
        self,
        kb_ids: list[int],
        predicates: list[str] | None = None,
        entity_ids: list[int] | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Candidate assertionök context építéshez."""
        ...
