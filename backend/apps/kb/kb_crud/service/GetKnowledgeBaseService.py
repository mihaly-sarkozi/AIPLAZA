from __future__ import annotations

# backend/apps/kb/kb_crud/service/GetKnowledgeBaseService.py
# Feladat: Egy tudástár lekérése use-case (láthatósági ellenőrzéssel).
# Sárközi Mihály - 2026.06.07

from typing import Any

from apps.kb.kb_crud.domain.CrudErrorCode import CrudErrorCode
from apps.kb.kb_crud.dto.KnowledgeBaseResponse import KnowledgeBaseResponse
from apps.kb.kb_crud.errors.CrudNotFoundError import CrudNotFoundError
from apps.kb.kb_crud.ports.KnowledgeBaseRepository import KnowledgeBaseRepository
from apps.kb.kb_crud.ports.StorageMetricsInterface import StorageMetricsInterface
from apps.kb.kb_crud.ports.TrainingSummaryInterface import TrainingSummaryInterface
from apps.kb.kb_crud.service.KbAccessPolicy import KbAccessPolicy
from apps.kb.kb_crud.service.KnowledgeBaseResponseMapper import to_response


class GetKnowledgeBaseService:
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

    async def execute(self, kb_uuid: str, *, current_user: Any) -> KnowledgeBaseResponse:
        kb = await self._repository.get_by_uuid(kb_uuid)
        if kb is None:
            raise CrudNotFoundError(CrudErrorCode.KB_NOT_FOUND)
        can_use = await self._access_policy.user_can_use(kb_uuid, current_user)
        can_train = await self._access_policy.user_can_train(kb_uuid, current_user)
        if not (can_use or can_train):
            # IDOR ellen: a nem látható tudástár "nem található".
            raise CrudNotFoundError(CrudErrorCode.KB_NOT_FOUND)
        return to_response(
            kb,
            can_train=can_train,
            has_training=self._training_summary.has_training(kb.uuid),
            storage_metrics=self._storage_metrics.metrics_for(kb),
        )


__all__ = ["GetKnowledgeBaseService"]
