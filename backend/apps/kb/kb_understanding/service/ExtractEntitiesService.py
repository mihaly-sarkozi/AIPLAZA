from __future__ import annotations

# backend/apps/kb/kb_understanding/service/ExtractEntitiesService.py
# Feladat: Entitások kinyerése a chunkokból az adapter-porton keresztül,
# szűrés + perzisztálás dokumentum-szintű replace szemantikával.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.KnowledgeChunkDto import KnowledgeChunkDto
from apps.kb.kb_understanding.dto.KnowledgeEntityDto import KnowledgeEntityDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.mapper.entity_mapper import entity_dto_to_orm
from apps.kb.kb_understanding.ports.EntityExtractorInterface import EntityExtractorInterface
from apps.kb.kb_understanding.repository.EntityRepository import EntityRepository
from apps.kb.kb_understanding.validation.ValidateEntities import ValidateEntities


class ExtractEntitiesService:
    def __init__(
        self,
        entity_repository: EntityRepository,
        entity_extractor: EntityExtractorInterface,
    ) -> None:
        self._entity_repository = entity_repository
        self._entity_extractor = entity_extractor
        self._validate = ValidateEntities()

    def run(
        self, ctx: UnderstandingJobContext, chunks: list[KnowledgeChunkDto]
    ) -> list[KnowledgeEntityDto]:
        extracted = self._entity_extractor.extract_entities(
            [(chunk.chunk_id, chunk.text) for chunk in chunks]
        )
        entities = self._validate(extracted)
        self._entity_repository.replace_for_document(
            ctx.training_item_id,
            [entity_dto_to_orm(ctx, entity) for entity in entities],
        )
        return entities


__all__ = ["ExtractEntitiesService"]
