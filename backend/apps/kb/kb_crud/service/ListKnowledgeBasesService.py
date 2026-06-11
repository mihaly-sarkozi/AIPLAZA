from __future__ import annotations

# backend/apps/kb/kb_crud/service/ListKnowledgeBasesService.py
# Feladat: Tudástár lista use-case — szerepkör szerinti láthatóság, can_train,
# has_training és tárhely metrikák kitöltése (a legacy /kb lista paritásával).
# Sárközi Mihály - 2026.06.07

from typing import Any

from apps.kb.kb_crud.domain.KnowledgeBase import KnowledgeBase
from apps.kb.kb_crud.dto.KnowledgeBaseResponse import KnowledgeBaseResponse
from apps.kb.kb_crud.ports.KnowledgeBaseRepository import KnowledgeBaseRepository
from apps.kb.kb_crud.ports.StorageMetricsInterface import StorageMetricsInterface
from apps.kb.kb_crud.ports.TrainingSummaryInterface import TrainingSummaryInterface
from apps.kb.kb_crud.service.KbAccessPolicy import KbAccessPolicy
from apps.kb.kb_crud.service.KnowledgeBaseResponseMapper import to_response


class ListKnowledgeBasesService:
    def __init__(
        self,
        repository: KnowledgeBaseRepository,
        access_policy: KbAccessPolicy,
        training_summary: TrainingSummaryInterface,
        storage_metrics: StorageMetricsInterface,
    ) -> None:
        self._repository = repository
        self._access_policy = access_policy
        self._training_summary = training_summary
        self._storage_metrics = storage_metrics

    async def execute(self, *, current_user: Any) -> list[KnowledgeBaseResponse]:
        knowledge_bases = await self._visible_knowledge_bases(current_user)
        trainable_ids = await self._access_policy.trainable_kb_ids(current_user)

        rows: list[KnowledgeBaseResponse] = []
        for kb in knowledge_bases:
            storage_metrics = self._storage_metrics.metrics_for(kb)
            training_char_count = int(
                storage_metrics.get("training_char_count")
                or kb.deleted_training_char_count
                or 0
            )
            if kb.is_deleted and training_char_count <= 0:
                continue
            rows.append(
                to_response(
                    kb,
                    can_train=bool(
                        not kb.is_deleted and kb.id is not None and kb.id in trainable_ids
                    ),
                    has_training=(
                        training_char_count > 0
                        if kb.is_deleted
                        else self._training_summary.has_training(kb.uuid)
                    ),
                    storage_metrics=storage_metrics,
                )
            )
        return sorted(rows, key=lambda row: row.deleted_at is not None)

    async def _visible_knowledge_bases(self, current_user: Any) -> list[KnowledgeBase]:
        if getattr(current_user, "id", None) is None:
            return []
        if self._access_policy.is_kb_manager(current_user):
            return await self._repository.list_all(
                include_deleted=self._access_policy.is_owner(current_user)
            )
        all_active = await self._repository.list_all()
        allowed_ids = await self._access_policy.usable_kb_ids(current_user)
        return [kb for kb in all_active if kb.id is not None and kb.id in allowed_ids]


__all__ = ["ListKnowledgeBasesService"]
