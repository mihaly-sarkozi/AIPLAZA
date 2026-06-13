from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.enums.DiscoveryStatus import DiscoveryStatus
from apps.kb.kb_discovery.repository.EntityRepository import EntityRepository
from apps.kb.kb_discovery.validation.ValidateDiscoveryResult import ValidateDiscoveryResult


class ValidateDiscoveryService:
    def __init__(self, entity_repository: EntityRepository) -> None:
        self._entity_repository = entity_repository
        self._validate = ValidateDiscoveryResult()

    def run(
        self,
        ctx: DiscoveryJobContext,
        *,
        chunks: list[DiscoveryChunkDto],
        chunk_count: int,
        had_optional_failures: bool = False,
    ) -> tuple[DiscoveryStatus, object]:
        entity_count = self._entity_repository.count_for_document(ctx.training_item_id)
        missing_chunk_language_count = sum(
            1 for chunk in chunks if not (chunk.language_code or "").strip()
        )
        checklist = self._validate(
            chunk_count=chunk_count,
            entity_count=entity_count,
            missing_chunk_language_count=missing_chunk_language_count,
        )
        if not checklist.core_complete:
            return DiscoveryStatus.FAILED, checklist
        if had_optional_failures or checklist.warnings:
            return DiscoveryStatus.PARTIAL, checklist
        return DiscoveryStatus.READY_FOR_EMBEDDING, checklist


__all__ = ["ValidateDiscoveryService"]
