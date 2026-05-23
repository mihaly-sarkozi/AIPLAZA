# backend/apps/knowledge/service/knowledge_permission_service.py
# Feladat: Knowledge modul kozponti permission boundary-je. Minden KB hasznalat,
# tanitas es permission lista dontes ezen a service-en megy at.

from __future__ import annotations

from typing import Any

from apps.knowledge.service.corpus_permission_service import CorpusPermissionService
from core.modules.auth.web.dependencies.auth_dependencies import has_permission


class KnowledgePermissionService(CorpusPermissionService):
    """Knowledge permission policy-k központi belépője."""

    def can_view_knowledge_base(self, user: Any | None, kb: Any | None) -> bool:
        user_id = self._user_id(user)
        kb_uuid = self._corpus_uuid(kb)
        if user_id is None or not kb_uuid:
            return False
        return self.user_can_use(kb_uuid, user_id, user) or self.user_can_train(kb_uuid, user_id, user)

    def can_view_knowledge_metrics(self, user: Any | None) -> bool:
        role = str(getattr(user, "role", "") or "").strip().lower()
        return role in {"owner", "admin"} or has_permission(user, "knowledge.metrics.view")

    def can_train_knowledge_base(self, user: Any | None, kb: Any | None) -> bool:
        user_id = self._user_id(user)
        kb_uuid = self._corpus_uuid(kb)
        if user_id is None or not kb_uuid:
            return False
        return self.user_can_train(kb_uuid, user_id, user)

    def can_delete_knowledge_base(self, user: Any | None, kb: Any | None) -> bool:
        if has_permission(user, "knowledge.delete"):
            return True
        return self.can_train_knowledge_base(user, kb)

    def can_view_ingest_run(self, user: Any | None, run: Any | None) -> bool:
        corpus_uuid = self._corpus_uuid(run)
        if not corpus_uuid:
            return False
        return self._can_use_or_train_corpus(user, corpus_uuid)

    def can_view_ingest_item(self, user: Any | None, item: Any | None) -> bool:
        corpus_uuid = self._corpus_uuid(item)
        if not corpus_uuid:
            return False
        return self._can_use_or_train_corpus(user, corpus_uuid)

    def can_reprocess_ingest_item(self, user: Any | None, item: Any | None) -> bool:
        corpus_uuid = self._corpus_uuid(item)
        if not corpus_uuid:
            return False
        return self._can_train_corpus(user, corpus_uuid)

    def can_delete_source(self, user: Any | None, source: Any | None) -> bool:
        corpus_uuid = self._corpus_uuid(source)
        if not corpus_uuid:
            return False
        if has_permission(user, "knowledge.source.delete"):
            return True
        return self._can_train_corpus(user, corpus_uuid)

    def can_start_index_build(self, user: Any | None, kb: Any | None) -> bool:
        return self.can_train_knowledge_base(user, kb)

    @staticmethod
    def _user_id(user: Any | None) -> int | None:
        user_id = getattr(user, "id", None)
        if user_id is None:
            return None
        try:
            return int(user_id)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _corpus_uuid(value: Any | None) -> str:
        if value is None:
            return ""
        return str(
            getattr(value, "corpus_uuid", None)
            or getattr(value, "kb_uuid", None)
            or getattr(value, "uuid", None)
            or ""
        ).strip()

    def _can_use_or_train_corpus(self, user: Any | None, corpus_uuid: str) -> bool:
        user_id = self._user_id(user)
        if user_id is None or not corpus_uuid:
            return False
        return self.user_can_use(corpus_uuid, user_id, user) or self.user_can_train(corpus_uuid, user_id, user)

    def _can_train_corpus(self, user: Any | None, corpus_uuid: str) -> bool:
        user_id = self._user_id(user)
        if user_id is None or not corpus_uuid:
            return False
        return self.user_can_train(corpus_uuid, user_id, user)


__all__ = ["KnowledgePermissionService"]
