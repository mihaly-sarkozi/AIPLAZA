from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import EntityMentionDto, KnowledgeEntityDto
from apps.kb.kb_discovery.entities.EntityRecognitionService import EntityRecognitionService
from apps.kb.kb_discovery.persons.PersonDirectoryProvider import PersonDirectoryProvider
from apps.kb.kb_discovery.persons.PersonRecognitionService import PersonRecognitionService
from apps.kb.kb_discovery.repository.EntityRepository import EntityMentionRepository, EntityRepository


class ExtractEntitiesService:
    def __init__(
        self,
        entity_repository: EntityRepository,
        mention_repository: EntityMentionRepository,
        *,
        person_directory=None,
    ) -> None:
        directory_provider = PersonDirectoryProvider(person_directory or [])
        self._person = PersonRecognitionService(
            entity_repository,
            mention_repository,
            directory_provider=directory_provider,
        )
        self._entity = EntityRecognitionService(entity_repository, mention_repository)
        self._entity_repository = entity_repository

    def run(
        self,
        ctx: DiscoveryJobContext,
        chunks: list[DiscoveryChunkDto],
    ) -> tuple[list[KnowledgeEntityDto], list[EntityMentionDto]]:
        person_entities, person_mentions = self._person.run(ctx, chunks)
        entities, mentions = self._entity.run(
            ctx,
            chunks,
            person_entities=person_entities,
            person_mentions=person_mentions,
        )
        return entities, mentions


__all__ = ["ExtractEntitiesService"]
