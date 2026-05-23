# backend/apps/knowledge/service/knowledge_pii_service.py
# Owns PII detection and corpus-scoped PII token mapping.

from __future__ import annotations

import logging
from typing import Any

from apps.knowledge.pii.pipeline import filter_pii
from apps.knowledge.repositories.pii_mapping_repository import KnowledgePiiMappingRepository

logger = logging.getLogger(__name__)


class KnowledgePiiService:
    def __init__(self, mapping_store: KnowledgePiiMappingRepository | None) -> None:
        self._mapping_store = mapping_store

    @property
    def mapping_store(self) -> KnowledgePiiMappingRepository | None:
        return self._mapping_store

    @classmethod
    def from_corpus_store(cls, corpus_store: Any) -> KnowledgePiiService:
        return cls(cls.init_mapping_store(corpus_store))

    @staticmethod
    def init_mapping_store(corpus_store: Any) -> KnowledgePiiMappingRepository | None:
        session_factory = getattr(corpus_store, "_sf", None)
        if session_factory is None:
            return None
        try:
            return KnowledgePiiMappingRepository(session_factory)
        except Exception:
            logger.debug("knowledge.pii_mapping_store.init_failed", exc_info=True)
            return None

    @staticmethod
    def detect_matches(*, text: str, sensitivity: str = "medium") -> list[tuple[int, int, str, str]]:
        return list(filter_pii(str(text or ""), str(sensitivity or "medium")))

    def resolve_or_create_token(self, *, corpus_uuid: str, entity_type: str, original_value: str) -> str:
        if self._mapping_store is None:
            return ""
        return self._mapping_store.resolve_or_create_token(
            corpus_uuid=corpus_uuid,
            entity_type=entity_type,
            original_value=original_value,
        )

    def resolve_tokens(self, *, corpus_uuid: str, tokens: list[str]) -> dict[str, str]:
        if self._mapping_store is None:
            return {}
        return self._mapping_store.resolve_tokens(corpus_uuid=corpus_uuid, tokens=tokens)


__all__ = ["KnowledgePiiService"]
