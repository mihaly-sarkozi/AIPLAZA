from __future__ import annotations

from collections import defaultdict

from apps.kb.kb_discovery.common.CandidateMerger import CandidateMerger
from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import EntityMentionDto, KnowledgeEntityDto
from apps.kb.kb_discovery.mapper.discovery_mapper import entity_dto_to_orm, mention_dto_to_orm
from apps.kb.kb_discovery.orm.EntityMention import EntityMention
from apps.kb.kb_discovery.orm.KnowledgeEntity import KnowledgeEntity
from apps.kb.kb_discovery.persons.PersonAliasRecognizer import PersonAliasRecognizer
from apps.kb.kb_discovery.persons.PersonDirectoryProvider import PersonDirectoryProvider
from apps.kb.kb_discovery.repository.EntityRepository import EntityMentionRepository, EntityRepository


class PersonRecognitionService:
    def __init__(
        self,
        entity_repository: EntityRepository,
        mention_repository: EntityMentionRepository,
        directory_provider: PersonDirectoryProvider | None = None,
        recognizer: PersonAliasRecognizer | None = None,
    ) -> None:
        self._entity_repository = entity_repository
        self._mention_repository = mention_repository
        self._directory_provider = directory_provider or PersonDirectoryProvider()
        self._recognizer = recognizer or PersonAliasRecognizer()
        self._merger = CandidateMerger()

    def run(
        self,
        ctx: DiscoveryJobContext,
        chunks: list[DiscoveryChunkDto],
        *,
        existing_entities: list[KnowledgeEntityDto] | None = None,
    ) -> tuple[list[KnowledgeEntityDto], list[EntityMentionDto]]:
        directory = self._directory_provider.load(
            tenant_slug=ctx.tenant_slug, knowledge_base_id=ctx.knowledge_base_id
        )
        context = DiscoveryContext(
            tenant_slug=ctx.tenant_slug,
            knowledge_base_id=ctx.knowledge_base_id,
            training_item_id=ctx.training_item_id,
            person_directory=directory,
        )
        candidates = self._merger.merge(self._recognizer.recognize(chunks, context))
        mentions: list[EntityMentionDto] = []
        entity_map: dict[tuple[str, str], KnowledgeEntityDto] = {}
        for candidate in candidates:
            mentions.append(
                EntityMentionDto(
                    entity_type=candidate.entity_type,
                    chunk_id=candidate.chunk_id,
                    raw_text=candidate.name,
                    normalized_name=candidate.normalized_name,
                    start_offset=candidate.start_offset,
                    end_offset=candidate.end_offset,
                    confidence=candidate.confidence,
                )
            )
            key = (candidate.entity_type.value, candidate.normalized_name)
            existing = entity_map.get(key)
            chunk_ids = tuple({*(existing.chunk_ids if existing else ()), candidate.chunk_id})
            entity_map[key] = KnowledgeEntityDto(
                entity_type=candidate.entity_type,
                name=candidate.name,
                normalized_name=candidate.normalized_name,
                confidence=max(existing.confidence if existing else 0.0, candidate.confidence),
                aliases=candidate.aliases,
                chunk_ids=chunk_ids,
            )
        entities = list(entity_map.values())
        if existing_entities:
            merged: dict[tuple[str, str], KnowledgeEntityDto] = {
                (e.entity_type.value, e.normalized_name): e for e in existing_entities
            }
            for entity in entities:
                key = (entity.entity_type.value, entity.normalized_name)
                if key in merged:
                    old = merged[key]
                    merged[key] = KnowledgeEntityDto(
                        entity_type=old.entity_type,
                        name=old.name,
                        normalized_name=old.normalized_name,
                        confidence=max(old.confidence, entity.confidence),
                        aliases=tuple(dict.fromkeys(old.aliases + entity.aliases)),
                        chunk_ids=tuple(dict.fromkeys(old.chunk_ids + entity.chunk_ids)),
                    )
                else:
                    merged[key] = entity
            entities = list(merged.values())
        orm_mentions = [mention_dto_to_orm(ctx, mention) for mention in mentions]
        self._mention_repository.replace_for_job(ctx.job_id, orm_mentions)
        return entities, mentions


__all__ = ["PersonRecognitionService"]
