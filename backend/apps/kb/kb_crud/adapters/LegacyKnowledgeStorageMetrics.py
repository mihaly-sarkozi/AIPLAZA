from __future__ import annotations

# backend/apps/kb/kb_crud/adapters/LegacyKnowledgeStorageMetrics.py
# Feladat: StorageMetricsInterface adapter — átmenetileg a legacy knowledge facade
# storage_metrics_for_corpus hívására delegál (file/db/qdrant metrikák).
# Sárközi Mihály - 2026.06.11

import logging
from typing import Any

from apps.kb.kb_crud.adapters.legacy_facade_resolver import resolve_legacy_knowledge_facade
from apps.kb.kb_crud.domain.KnowledgeBase import KnowledgeBase

logger = logging.getLogger(__name__)


class LegacyKnowledgeStorageMetrics:
    def metrics_for(self, kb: KnowledgeBase) -> dict[str, int]:
        facade: Any = resolve_legacy_knowledge_facade()
        if facade is None:
            return {}
        try:
            value = facade.storage_metrics_for_corpus(kb)
        except Exception:
            logger.debug("kb_crud.storage_metrics_failed", exc_info=True)
            return {}
        return value if isinstance(value, dict) else {}


__all__ = ["LegacyKnowledgeStorageMetrics"]
