# backend/apps/knowledge/service/knowledge_permission_service.py
# Feladat: Knowledge modul kozponti permission boundary-je. Minden KB hasznalat,
# tanitas es permission lista dontes ezen a service-en megy at.

from __future__ import annotations

from typing import Any

from apps.knowledge.service.corpus_permission_service import CorpusPermissionService


class KnowledgePermissionService(CorpusPermissionService):
    """Knowledge permission policy-k központi belépője."""

    def can_view_knowledge_metrics(self, user: Any | None) -> bool:
        role = str(getattr(user, "role", "") or "").strip().lower()
        return role in {"owner", "admin"}

    def can_train_knowledge_base(self, user: Any | None, kb: Any | None) -> bool:
        if user is None or kb is None:
            return False
        user_id = getattr(user, "id", None)
        kb_uuid = str(getattr(kb, "uuid", "") or "").strip()
        if user_id is None or not kb_uuid:
            return False
        return self.user_can_train(kb_uuid, int(user_id), user)


__all__ = ["KnowledgePermissionService"]
