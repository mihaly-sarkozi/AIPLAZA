from __future__ import annotations

# backend/apps/kb/kb_crud/adapters/LegacyKnowledgeTrainingSummary.py
# Feladat: TrainingSummaryInterface adapter — átmenetileg a legacy knowledge facade
# ingest run lekérdezéseire delegál (van-e tanítás, tanított karakterszám).
# Sárközi Mihály - 2026.06.11

import logging
from typing import Any

from apps.kb.kb_crud.adapters.legacy_facade_resolver import resolve_legacy_knowledge_facade

logger = logging.getLogger(__name__)


class LegacyKnowledgeTrainingSummary:
    def has_training(self, kb_uuid: str) -> bool:
        facade: Any = resolve_legacy_knowledge_facade()
        if facade is None:
            return False
        try:
            return bool(facade.list_ingest_runs(kb_uuid, limit=1))
        except Exception:
            logger.debug("kb_crud.has_training_failed", exc_info=True)
            return False

    def training_char_count(self, kb_uuid: str) -> int:
        facade: Any = resolve_legacy_knowledge_facade()
        if facade is None:
            return 0
        try:
            return int(facade.ingest_run_list_summary(kb_uuid).get("total_char_count") or 0)
        except Exception:
            logger.debug("kb_crud.training_char_count_failed", exc_info=True)
            return 0


__all__ = ["LegacyKnowledgeTrainingSummary"]
