from __future__ import annotations

import logging
import uuid as uuid_lib
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from apps.knowledge.domain.corpus import Corpus
from apps.knowledge.errors import KnowledgeBaseNotFound, KnowledgeValidationError
from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.infrastructure.audit.service.audit_service import AuditService

logger = logging.getLogger(__name__)


class CorpusManagementService:
    def __init__(
        self,
        *,
        corpus_store: Any,
        metrics_store: Any,
        ingest_input_store: Any,
        index_build_store: Any,
        vector_index_factory: Callable[[], Any],
        ingest_run_list_summary: Callable[[str], dict[str, Any]],
        clear_contents: Callable[..., dict[str, int]],
        log_step: Callable[..., None],
        audit_service: AuditService | None = None,
    ) -> None:
        self._corpus_store = corpus_store
        self._metrics_store = metrics_store
        self._ingest_input_store = ingest_input_store
        self._index_build_store = index_build_store
        self._vector_index_factory = vector_index_factory
        self._ingest_run_list_summary = ingest_run_list_summary
        self._clear_contents = clear_contents
        self._log_step = log_step
        self._audit = audit_service

    @staticmethod
    def to_corpus(item: Any, *, tenant: str = "") -> Corpus:
        return Corpus(
            id=getattr(item, "id", None),
            tenant=tenant,
            uuid=str(getattr(item, "uuid")),
            name=str(getattr(item, "name")),
            description=getattr(item, "description", None),
            qdrant_collection_name=str(getattr(item, "qdrant_collection_name")),
            created_at=getattr(item, "created_at", None),
            updated_at=getattr(item, "updated_at", None),
            personal_data_mode=str(getattr(item, "personal_data_mode", "no_personal_data")),
            personal_data_sensitivity=str(getattr(item, "personal_data_sensitivity", "medium")),
            pii_depersonalization_enabled=bool(getattr(item, "pii_depersonalization_enabled", True)),
            public_enabled=bool(getattr(item, "public_enabled", False)),
            deleted_at=getattr(item, "deleted_at", None),
            deleted_display_name=getattr(item, "deleted_display_name", None),
            deleted_training_char_count=max(0, int(getattr(item, "deleted_training_char_count", 0) or 0)),
        )

    def list_all_unfiltered(self) -> list[Corpus]:
        return [self.to_corpus(item) for item in self._corpus_store.list_all()]

    def require_corpus(self, corpus_uuid: str) -> Corpus:
        raw = self._corpus_store.get_by_uuid(corpus_uuid)
        if raw is None:
            raise KnowledgeBaseNotFound()
        return self.to_corpus(raw)

    def qdrant_collection_for_uuid(self, kb_uuid: str) -> str | None:
        kb = self._corpus_store.get_by_uuid(kb_uuid)
        return str(getattr(kb, "qdrant_collection_name")) if kb else None

    def create(
        self,
        *,
        name: str,
        description: str | None,
        permissions: list[tuple[int, str]] | None,
        pii_depersonalization_enabled: bool,
        current_user_id: int | None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> Corpus:
        if self._corpus_store.get_by_name(name):
            raise KnowledgeValidationError("Knowledge base name already exists.")
        if current_user_id is None:
            raise KnowledgeValidationError("Current user is required.")
        corpus_uuid = str(uuid_lib.uuid4())
        corpus = Corpus(
            id=None,
            tenant="",
            uuid=corpus_uuid,
            name=name,
            description=description,
            qdrant_collection_name=f"kb_{corpus_uuid}",
            pii_depersonalization_enabled=bool(pii_depersonalization_enabled),
            created_at=None,
            updated_at=None,
        )
        created = self.to_corpus(self._corpus_store.create(corpus, actor_user_id=current_user_id))
        perms = [(uid, perm) for uid, perm in (permissions or []) if perm and perm != "none"]
        if not any(uid == current_user_id for uid, _ in perms):
            perms.append((current_user_id, "train"))
        self._corpus_store.set_permissions(created.uuid, perms, actor_user_id=current_user_id)
        self._audit_created(created, current_user_id, ip=ip, user_agent=user_agent)
        self._audit_initial_permissions(created, perms, current_user_id, ip=ip, user_agent=user_agent)
        self._metrics_store.increment("corpus_count", 1)
        self._log_step("corpus.create", status="ok", corpus_uuid=created.uuid, permissions=len(perms))
        return created

    def update(
        self,
        *,
        uuid: str,
        name: str,
        description: str | None,
        personal_data_mode: str | None,
        pii_depersonalization_enabled: bool | None,
        public_enabled: bool | None,
        current_user_id: int | None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> Corpus:
        raw = self._corpus_store.get_by_uuid(uuid)
        if not raw:
            raise KnowledgeBaseNotFound()
        if current_user_id is None:
            raise KnowledgeValidationError("Current user is required.")
        corpus = self.to_corpus(raw)
        updated = replace(
            corpus,
            name=name,
            description=description,
            personal_data_mode=personal_data_mode or corpus.personal_data_mode,
            pii_depersonalization_enabled=(
                bool(pii_depersonalization_enabled)
                if pii_depersonalization_enabled is not None
                else corpus.pii_depersonalization_enabled
            ),
            public_enabled=bool(public_enabled) if public_enabled is not None else corpus.public_enabled,
        )
        saved = self.to_corpus(self._corpus_store.update(updated, actor_user_id=current_user_id))
        self._audit_setting_changes(corpus, saved, current_user_id, ip=ip, user_agent=user_agent)
        return saved

    def _audit_setting_changes(
        self,
        old: Corpus,
        new: Corpus,
        actor_user_id: int | None,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        if self._audit is None:
            return
        fields = (
            ("public_enabled", old.public_enabled, new.public_enabled),
            ("pii_depersonalization_enabled", old.pii_depersonalization_enabled, new.pii_depersonalization_enabled),
        )
        for field, old_value, new_value in fields:
            if bool(old_value) == bool(new_value):
                continue
            self._audit.log(
                AuditLogAction.KNOWLEDGE_SETTING_CHANGED,
                user_id=actor_user_id,
                target_type="knowledge_base",
                target_id=new.uuid,
                details={
                    "kb_uuid": new.uuid,
                    "kb_name": new.name,
                    "field": field,
                    "old_value": bool(old_value),
                    "new_value": bool(new_value),
                    "changed_by": actor_user_id,
                },
                ip=ip,
                user_agent=user_agent,
            )

    def delete(
        self,
        uuid: str,
        *,
        confirm_name: str | None = None,
        current_user_id: int | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        raw = self._corpus_store.get_by_uuid(uuid)
        if not raw:
            raise KnowledgeBaseNotFound()
        corpus = self.to_corpus(raw)
        if confirm_name and confirm_name != str(getattr(raw, "name", "") or ""):
            raise KnowledgeValidationError("Confirmation name does not match.")
        training_char_count = int(self._ingest_run_list_summary(uuid).get("total_char_count") or 0)
        self._clear_contents(uuid, confirm_name=confirm_name)
        self._corpus_store.delete(uuid, training_char_count=training_char_count)
        self._audit_deleted(corpus, current_user_id, training_char_count=training_char_count, ip=ip, user_agent=user_agent)
        self._log_step("corpus.delete", status="ok", corpus_uuid=uuid, training_char_count=training_char_count)

    def _audit_created(
        self,
        corpus: Corpus,
        actor_user_id: int | None,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        if self._audit is None:
            return
        self._audit.log(
            AuditLogAction.KNOWLEDGE_CREATED,
            user_id=actor_user_id,
            target_type="knowledge_base",
            target_id=corpus.uuid,
            details={
                "kb_uuid": corpus.uuid,
                "kb_name": corpus.name,
                "changed_by": actor_user_id,
                "pii_depersonalization_enabled": bool(corpus.pii_depersonalization_enabled),
                "public_enabled": bool(corpus.public_enabled),
            },
            ip=ip,
            user_agent=user_agent,
        )

    def _audit_deleted(
        self,
        corpus: Corpus,
        actor_user_id: int | None,
        *,
        training_char_count: int,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        if self._audit is None:
            return
        self._audit.log(
            AuditLogAction.KNOWLEDGE_DELETED,
            user_id=actor_user_id,
            target_type="knowledge_base",
            target_id=corpus.uuid,
            details={
                "kb_uuid": corpus.uuid,
                "kb_name": corpus.name,
                "changed_by": actor_user_id,
                "training_char_count": training_char_count,
            },
            ip=ip,
            user_agent=user_agent,
        )

    def _audit_initial_permissions(
        self,
        corpus: Corpus,
        permissions: list[tuple[int, str]],
        actor_user_id: int | None,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        if self._audit is None:
            return
        for user_id, permission in sorted(permissions):
            if not permission or permission == "none":
                continue
            self._audit.log(
                AuditLogAction.KNOWLEDGE_PERMISSION_CHANGED,
                user_id=int(user_id),
                target_type="knowledge_base",
                target_id=corpus.uuid,
                details={
                    "kb_uuid": corpus.uuid,
                    "kb_name": corpus.name,
                    "old_permission": "none",
                    "new_permission": permission,
                    "changed_by": actor_user_id,
                },
                ip=ip,
                user_agent=user_agent,
            )

    def storage_metrics_for_corpus(self, corpus: Corpus) -> dict[str, Any]:
        if getattr(corpus, "deleted_at", None) is not None:
            return self._deleted_storage_metrics(corpus)
        file_bytes = self._file_storage_bytes(corpus.uuid)
        database_bytes = self._database_storage_bytes(corpus.uuid)
        qdrant_bytes, qdrant_points, qdrant_vectors = self._qdrant_storage_metrics(corpus)
        training_char_count = self._training_char_count(corpus.uuid)
        total_bytes = file_bytes + database_bytes + qdrant_bytes
        return {
            "file_bytes": max(0, file_bytes),
            "database_bytes": max(0, database_bytes),
            "qdrant_bytes": max(0, qdrant_bytes),
            "total_bytes": max(0, total_bytes),
            "qdrant_points": max(0, qdrant_points),
            "qdrant_vectors": max(0, qdrant_vectors),
            "training_char_count": max(0, training_char_count),
        }

    @staticmethod
    def _deleted_storage_metrics(corpus: Corpus) -> dict[str, Any]:
        return {
            "file_bytes": 0,
            "database_bytes": 0,
            "qdrant_bytes": 0,
            "total_bytes": 0,
            "qdrant_points": 0,
            "qdrant_vectors": 0,
            "training_char_count": max(0, int(getattr(corpus, "deleted_training_char_count", 0) or 0)),
        }

    def _file_storage_bytes(self, corpus_uuid: str) -> int:
        if not hasattr(self._ingest_input_store, "uploaded_file_size_bytes_for_corpus"):
            return 0
        try:
            return int(self._ingest_input_store.uploaded_file_size_bytes_for_corpus(corpus_uuid))
        except Exception:
            logger.debug("knowledge.storage_metrics.file_bytes_failed", exc_info=True)
            return 0

    def _database_storage_bytes(self, corpus_uuid: str) -> int:
        if not hasattr(self._corpus_store, "database_size_bytes_for_corpus"):
            return 0
        try:
            return int(self._corpus_store.database_size_bytes_for_corpus(corpus_uuid))
        except Exception:
            logger.debug("knowledge.storage_metrics.database_bytes_failed", exc_info=True)
            return 0

    def _qdrant_storage_metrics(self, corpus: Corpus) -> tuple[int, int, int]:
        collection_names = {str(corpus.qdrant_collection_name or "").strip()}
        collection_names.update(
            str(build.collection_name or "").strip()
            for build in self._index_build_store.list_for_corpus(corpus.uuid)
            if str(build.collection_name or "").strip()
        )
        collection_names.discard("")
        if not collection_names:
            return 0, 0, 0
        try:
            stats_fn = getattr(self._vector_index_factory(), "collection_storage_stats", None)
            if not callable(stats_fn):
                return 0, 0, 0
            bytes_total = points_total = vectors_total = 0
            for collection_name in collection_names:
                stats = stats_fn(collection_name)
                bytes_total += int(stats.get("estimated_bytes") or 0)
                points_total += int(stats.get("points_count") or 0)
                vectors_total += int(stats.get("vectors_count") or 0)
            return bytes_total, points_total, vectors_total
        except Exception:
            logger.debug("knowledge.storage_metrics.qdrant_bytes_failed", exc_info=True)
            return 0, 0, 0

    def _training_char_count(self, corpus_uuid: str) -> int:
        try:
            return int(self._ingest_run_list_summary(corpus_uuid).get("total_char_count") or 0)
        except Exception:
            logger.debug("knowledge.storage_metrics.training_chars_failed", exc_info=True)
            return 0


__all__ = ["CorpusManagementService"]
