from __future__ import annotations

from apps.kb.kb_discovery.common.CandidateMerger import CandidateMerger
from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import EntityMentionDto, KnowledgeEntityDto
from apps.kb.kb_discovery.gazetteers.GivenNameGazetteer import GivenNameGazetteer
from apps.kb.kb_discovery.mapper.discovery_mapper import mention_dto_from_candidate, mention_dto_to_orm
from apps.kb.kb_discovery.persons.FullPersonNameRecognizer import FullPersonNameRecognizer
from apps.kb.kb_discovery.persons.GivenNameRecognizer import GivenNameRecognizer
from apps.kb.kb_discovery.persons.PersonAliasRecognizer import PersonAliasRecognizer
from apps.kb.kb_discovery.persons.PersonCandidateFilter import PersonCandidateFilter
from apps.kb.kb_discovery.persons.PersonConfidenceScorer import PERSON_ENTITY_MIN_CONFIDENCE
from apps.kb.kb_discovery.persons.PersonDirectoryProvider import PersonDirectoryProvider
from apps.kb.kb_discovery.repository.EntityRepository import EntityMentionRepository, EntityRepository


class PersonRecognitionService:
    def __init__(
        self,
        entity_repository: EntityRepository,
        mention_repository: EntityMentionRepository,
        directory_provider: PersonDirectoryProvider | None = None,
        alias_recognizer: PersonAliasRecognizer | None = None,
        given_name_recognizer: GivenNameRecognizer | None = None,
        full_name_recognizer: FullPersonNameRecognizer | None = None,
        given_name_gazetteer: GivenNameGazetteer | None = None,
    ) -> None:
        self._entity_repository = entity_repository
        self._mention_repository = mention_repository
        self._directory_provider = directory_provider or PersonDirectoryProvider()
        gazetteer = given_name_gazetteer or GivenNameGazetteer()
        self._alias_recognizer = alias_recognizer or PersonAliasRecognizer()
        self._given_name_recognizer = given_name_recognizer or GivenNameRecognizer(gazetteer)
        self._full_name_recognizer = full_name_recognizer or FullPersonNameRecognizer(gazetteer)
        self._merger = CandidateMerger()
        self._candidate_filter = PersonCandidateFilter()

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
        chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        alias_candidates = self._alias_recognizer.recognize(chunks, context)
        given_candidates = self._given_name_recognizer.recognize(chunks, context)
        full_name_candidates = self._full_name_recognizer.recognize(chunks, context)
        filtered = self._candidate_filter.filter(
            alias_candidates + given_candidates + full_name_candidates
        )
        merged = self._merger.merge(filtered)

        mentions: list[EntityMentionDto] = []
        entity_map: dict[tuple[str, str], KnowledgeEntityDto] = {}
        for candidate in merged:
            if candidate.confidence < PERSON_ENTITY_MIN_CONFIDENCE:
                continue
            chunk = chunk_by_id.get(candidate.chunk_id)
            mentions.append(mention_dto_from_candidate(ctx, chunk, candidate))
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
            merged_entities: dict[tuple[str, str], KnowledgeEntityDto] = {
                (e.entity_type.value, e.normalized_name): e for e in existing_entities
            }
            for entity in entities:
                key = (entity.entity_type.value, entity.normalized_name)
                if key in merged_entities:
                    old = merged_entities[key]
                    merged_entities[key] = KnowledgeEntityDto(
                        entity_type=old.entity_type,
                        name=old.name,
                        normalized_name=old.normalized_name,
                        confidence=max(old.confidence, entity.confidence),
                        aliases=tuple(dict.fromkeys(old.aliases + entity.aliases)),
                        chunk_ids=tuple(dict.fromkeys(old.chunk_ids + entity.chunk_ids)),
                    )
                else:
                    merged_entities[key] = entity
            entities = list(merged_entities.values())

        orm_mentions = [mention_dto_to_orm(ctx, mention) for mention in mentions]
        self._mention_repository.replace_for_job(ctx.job_id, orm_mentions)
        return entities, mentions


__all__ = ["PersonRecognitionService"]
