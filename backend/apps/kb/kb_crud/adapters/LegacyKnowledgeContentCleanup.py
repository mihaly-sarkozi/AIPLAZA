from __future__ import annotations

# backend/apps/kb/kb_crud/adapters/LegacyKnowledgeContentCleanup.py
# Feladat: ContentCleanupInterface adapter — átmenetileg a legacy knowledge facade
# clear_contents hívására delegál (DB + Qdrant + object storage ürítés).
# Sárközi Mihály - 2026.06.11

from typing import Any

from apps.kb.kb_crud.adapters.legacy_facade_resolver import resolve_legacy_knowledge_facade


class LegacyKnowledgeContentCleanup:
    def clear_contents(self, kb_uuid: str, *, confirm_name: str | None = None) -> dict[str, int]:
        facade: Any = resolve_legacy_knowledge_facade()
        if facade is None:
            return {}
        return facade.clear_contents(kb_uuid, confirm_name=confirm_name)


__all__ = ["LegacyKnowledgeContentCleanup"]
