from __future__ import annotations

from apps.knowledge.service.facade_mixin_imports import *  # noqa: F401,F403


class CorpusFacadeMixin:
    def list_all(self, current_user_id: int | None = None, current_user: User | None = None) -> list[Corpus]:
        return self._knowledge_permission_service.list_all(
            current_user_id=current_user_id,
            current_user=current_user,
        )

    def list_all_unfiltered(self) -> list[Corpus]:
        return self._corpus_management_service.list_all_unfiltered()

    def storage_metrics_for_corpus(self, corpus: Corpus) -> dict[str, Any]:
        return self._corpus_management_service.storage_metrics_for_corpus(corpus)

    def qdrant_collection_for_uuid(self, kb_uuid: str) -> str | None:
        return self._corpus_management_service.qdrant_collection_for_uuid(kb_uuid)

    def detect_pii_matches(self, *, text: str, sensitivity: str = "medium") -> list[tuple[int, int, str, str]]:
        return self._knowledge_pii_service.detect_matches(text=text, sensitivity=sensitivity)

    def resolve_or_create_pii_token(self, *, corpus_uuid: str, entity_type: str, original_value: str) -> str:
        return self._knowledge_pii_service.resolve_or_create_token(
            corpus_uuid=corpus_uuid,
            entity_type=entity_type,
            original_value=original_value,
        )

    def resolve_pii_tokens(self, *, corpus_uuid: str, tokens: list[str]) -> dict[str, str]:
        return self._knowledge_pii_service.resolve_tokens(corpus_uuid=corpus_uuid, tokens=tokens)

    def get_trainable_kb_ids(self, user_id: int, user: User | None) -> set[int]:
        return self._knowledge_permission_service.get_trainable_kb_ids(user_id, user)

    def create(
        self,
        name: str,
        description: str | None = None,
        permissions: list[tuple[int, str]] | None = None,
        pii_depersonalization_enabled: bool = True,
        current_user_id: int | None = None,
    ) -> Corpus:
        return self._corpus_management_service.create(
            name=name,
            description=description,
            permissions=permissions,
            pii_depersonalization_enabled=pii_depersonalization_enabled,
            current_user_id=current_user_id,
        )

    def update(
        self,
        uuid: str,
        name: str,
        description: str | None,
        personal_data_mode: str | None = None,
        pii_depersonalization_enabled: bool | None = None,
        current_user_id: int | None = None,
    ) -> Corpus:
        return self._corpus_management_service.update(
            uuid=uuid,
            name=name,
            description=description,
            personal_data_mode=personal_data_mode,
            pii_depersonalization_enabled=pii_depersonalization_enabled,
            current_user_id=current_user_id,
        )

    def delete(self, uuid: str, confirm_name: str | None = None, demo_mode: bool = False) -> None:
        self._corpus_management_service.delete(uuid, confirm_name=confirm_name)

    def clear_contents(
        self,
        uuid: str,
        *,
        confirm_name: str | None = None,
        current_user_id: int | None = None,
    ) -> dict[str, int]:
        return self._knowledge_cleanup_service.clear_contents(
            uuid,
            confirm_name=confirm_name,
            current_user_id=current_user_id,
        )

    def get_permissions_with_users(self, kb_uuid: str) -> list[dict[str, Any]]:
        return self._knowledge_permission_service.get_permissions_with_users(kb_uuid)

    def get_permissions_with_users_batch(self, kb_uuids: list[str]) -> dict[str, list[dict[str, Any]]]:
        return self._knowledge_permission_service.get_permissions_with_users_batch(kb_uuids)

    def set_permissions(
        self,
        kb_uuid: str,
        permissions: list[tuple[int, str]],
        current_user_id: int | None = None,
    ) -> None:
        self._knowledge_permission_service.set_permissions(
            kb_uuid,
            permissions,
            current_user_id=current_user_id,
        )

    def user_can_use(self, kb_uuid: str, user_id: int, user: User | None) -> bool:
        return self._knowledge_permission_service.user_can_use(kb_uuid, user_id, user)

    def user_can_train(self, kb_uuid: str, user_id: int, user: User | None) -> bool:
        return self._knowledge_permission_service.user_can_train(kb_uuid, user_id, user)

    def can_view_knowledge_base(self, user: User | None, kb: Corpus | None) -> bool:
        return self._knowledge_permission_service.can_view_knowledge_base(user, kb)

    def can_train_knowledge_base(self, user: User | None, kb: Corpus | None) -> bool:
        return self._knowledge_permission_service.can_train_knowledge_base(user, kb)

    def can_delete_knowledge_base(self, user: User | None, kb: Corpus | None) -> bool:
        return self._knowledge_permission_service.can_delete_knowledge_base(user, kb)

    def can_view_ingest_run(self, user: User | None, run: Any | None) -> bool:
        return self._knowledge_permission_service.can_view_ingest_run(user, run)

    def can_view_ingest_item(self, user: User | None, item: Any | None) -> bool:
        return self._knowledge_permission_service.can_view_ingest_item(user, item)

    def can_reprocess_ingest_item(self, user: User | None, item: Any | None) -> bool:
        return self._knowledge_permission_service.can_reprocess_ingest_item(user, item)

    def can_delete_source(self, user: User | None, source: Any | None) -> bool:
        return self._knowledge_permission_service.can_delete_source(user, source)

    def can_start_index_build(self, user: User | None, kb: Corpus | None) -> bool:
        return self._knowledge_permission_service.can_start_index_build(user, kb)

    def can_view_knowledge_metrics(self, user: User | None) -> bool:
        return self._knowledge_permission_service.can_view_knowledge_metrics(user)


__all__ = ["CorpusFacadeMixin"]
