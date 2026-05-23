# backend/apps/knowledge/service/knowledge_permission_service.py
# Feladat: Knowledge modul kozponti permission boundary-je. Minden KB hasznalat,
# tanitas es permission lista dontes ezen a service-en megy at.

from __future__ import annotations

from typing import Any

from apps.knowledge.service.corpus_permission_service import CorpusPermissionService
from core.modules.auth.web.dependencies.auth_dependencies import has_permission


def _safe_has_permission(user: Any | None, permission: str) -> bool:
    try:
        return has_permission(user, permission)
    except RuntimeError:
        return False


class KnowledgePermissionService(CorpusPermissionService):
    """Knowledge permission policy-k központi belépője."""

    def can_view_knowledge_base(self, user: Any | None, kb: Any | None) -> bool:
        user_id = self._user_id(user)
        kb_uuid = self._corpus_uuid(kb)
        if user_id is None or not kb_uuid:
            return False
        if not self._tenant_allows(user, kb):
            return False
        if self._has_role(user, {"owner"}) or _safe_has_permission(user, "knowledge.read"):
            return True
        return self.user_can_use(kb_uuid, user_id, user) or self.user_can_train(kb_uuid, user_id, user)

    def can_view_knowledge_metrics(self, user: Any | None) -> bool:
        role = str(getattr(user, "role", "") or "").strip().lower()
        return role in {"owner", "admin"} or _safe_has_permission(user, "knowledge.metrics.view")

    def can_train_knowledge_base(self, user: Any | None, kb: Any | None) -> bool:
        user_id = self._user_id(user)
        kb_uuid = self._corpus_uuid(kb)
        if user_id is None or not kb_uuid:
            return False
        if not self._tenant_allows(user, kb):
            return False
        if self._has_role(user, {"owner"}) or _safe_has_permission(user, "knowledge.write"):
            return True
        return self.user_can_train(kb_uuid, user_id, user)

    def can_delete_knowledge_base(self, user: Any | None, kb: Any | None) -> bool:
        if not self._tenant_allows(user, kb):
            return False
        if self._has_role(user, {"owner"}) or _safe_has_permission(user, "knowledge.delete"):
            return True
        return self.can_train_knowledge_base(user, kb)

    def can_view_ingest_run(self, user: Any | None, run: Any | None) -> bool:
        corpus_uuid = self._corpus_uuid(run)
        if not corpus_uuid:
            return False
        if not self._tenant_allows(user, run):
            return False
        if self._has_role(user, {"owner"}):
            return True
        return self._can_use_or_train_corpus(user, corpus_uuid)

    def can_view_ingest_item(self, user: Any | None, item: Any | None) -> bool:
        corpus_uuid = self._corpus_uuid(item)
        if not corpus_uuid:
            return False
        if not self._tenant_allows(user, item):
            return False
        return self._can_use_or_train_corpus(user, corpus_uuid)

    def can_reprocess_ingest_item(self, user: Any | None, item: Any | None) -> bool:
        corpus_uuid = self._corpus_uuid(item)
        if not corpus_uuid:
            return False
        if not self._tenant_allows(user, item):
            return False
        if self._has_role(user, {"owner"}):
            return True
        return self._can_train_corpus(user, corpus_uuid)

    def can_delete_source(self, user: Any | None, source: Any | None) -> bool:
        corpus_uuid = self._corpus_uuid(source)
        if not corpus_uuid:
            return False
        if not self._tenant_allows(user, source):
            return False
        if self._has_role(user, {"owner"}) or _safe_has_permission(user, "knowledge.source.delete"):
            return True
        return self._can_train_corpus(user, corpus_uuid)

    def can_start_index_build(self, user: Any | None, kb: Any | None) -> bool:
        return self.can_train_knowledge_base(user, kb)

    @staticmethod
    def _has_role(user: Any | None, roles: set[str]) -> bool:
        return str(getattr(user, "role", "") or "").strip().lower() in roles

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

    @classmethod
    def _tenant_key(cls, value: Any | None) -> str:
        if value is None:
            return ""
        raw = (
            getattr(value, "tenant", None)
            or getattr(value, "tenant_slug", None)
            or getattr(value, "tenant_id", None)
        )
        if raw is None and isinstance(value, dict):
            raw = value.get("tenant") or value.get("tenant_slug") or value.get("tenant_id")
        if raw is not None and not isinstance(raw, str):
            raw = getattr(raw, "slug", None) or getattr(raw, "id", None) or raw
        return str(raw or "").strip()

    @classmethod
    def _tenant_allows(cls, user: Any | None, resource: Any | None) -> bool:
        if cls._has_role(user, {"owner"}):
            return True
        user_tenant = cls._tenant_key(user)
        resource_tenant = cls._tenant_key(resource)
        if not user_tenant or not resource_tenant:
            return True
        return user_tenant == resource_tenant

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
