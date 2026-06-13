from __future__ import annotations

from apps.kb.kb_discovery.common.CandidateMerger import CandidateMerger
from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import EntityMentionDto, KnowledgeEntityDto
from apps.kb.kb_discovery.entities.DictionaryEntityRecognizer import (
    DictionaryEntityRecognizer,
    SystemNameRecognizer,
)
from apps.kb.kb_discovery.entities.IdentifierRecognizer import IdentifierRecognizer
from apps.kb.kb_discovery.entities.LegalFormCompanyRecognizer import LegalFormCompanyRecognizer
from apps.kb.kb_discovery.entities.providers.EntityDictionaryProvider import (
    CompositeEntityDictionaryProvider,
    build_default_entity_dictionary_provider,
)
from apps.kb.kb_discovery.gazetteers.LegalFormGazetteer import LegalFormGazetteer
from apps.kb.kb_discovery.gazetteers.SystemsGazetteer import SystemsGazetteer
from apps.kb.kb_discovery.mapper.discovery_mapper import (
    entity_dto_to_orm,
    mention_dto_from_candidate,
    mention_dto_to_orm,
)
from apps.kb.kb_discovery.repository.EntityRepository import EntityMentionRepository, EntityRepository


class EntityRecognitionService:
    def __init__(
        self,
        entity_repository: EntityRepository,
        mention_repository: EntityMentionRepository,
        *,
        entity_dictionary_provider: CompositeEntityDictionaryProvider | None = None,
        systems_gazetteer: SystemsGazetteer | None = None,
        legal_form_gazetteer: LegalFormGazetteer | None = None,
    ) -> None:
        self._entity_repository = entity_repository
        self._mention_repository = mention_repository
        self._entity_dictionary_provider = (
            entity_dictionary_provider or build_default_entity_dictionary_provider()
        )
        systems = systems_gazetteer or SystemsGazetteer()
        legal_forms = legal_form_gazetteer or LegalFormGazetteer()
        self._merger = CandidateMerger()
        self._recognizers = [
            LegalFormCompanyRecognizer(legal_forms),
            SystemNameRecognizer(systems),
            DictionaryEntityRecognizer(),
            IdentifierRecognizer(),
        ]

    def run(
        self,
        ctx: DiscoveryJobContext,
        chunks: list[DiscoveryChunkDto],
        *,
        person_entities: list[KnowledgeEntityDto] | None = None,
        person_mentions: list[EntityMentionDto] | None = None,
    ) -> tuple[list[KnowledgeEntityDto], list[EntityMentionDto], list[dict]]:
        context = DiscoveryContext(
            tenant_slug=ctx.tenant_slug,
            knowledge_base_id=ctx.knowledge_base_id,
            training_item_id=ctx.training_item_id,
            entity_dictionary=self._entity_dictionary_provider.load(
                tenant_slug=ctx.tenant_slug,
                knowledge_base_id=ctx.knowledge_base_id,
            ),
        )
        chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        candidates = []
        for recognizer in self._recognizers:
            candidates.extend(recognizer.recognize(chunks, context))
        candidates = self._merger.merge(candidates)

        entity_map: dict[tuple[str, str], KnowledgeEntityDto] = {}
        mentions: list[EntityMentionDto] = list(person_mentions or [])

        for candidate in candidates:
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

        for person in person_entities or []:
            key = (person.entity_type.value, person.normalized_name)
            if key in entity_map:
                old = entity_map[key]
                entity_map[key] = KnowledgeEntityDto(
                    entity_type=old.entity_type,
                    name=old.name,
                    normalized_name=old.normalized_name,
                    confidence=max(old.confidence, person.confidence),
                    aliases=tuple(dict.fromkeys(old.aliases + person.aliases)),
                    chunk_ids=tuple(dict.fromkeys(old.chunk_ids + person.chunk_ids)),
                )
            else:
                entity_map[key] = person

        entities = list(entity_map.values())
        self._entity_repository.replace_for_document(
            ctx.training_item_id, [entity_dto_to_orm(ctx, entity) for entity in entities]
        )
        self._mention_repository.replace_for_job(
            ctx.job_id, [mention_dto_to_orm(ctx, mention) for mention in mentions]
        )
        return entities, mentions, list(context.dictionary_warnings)


__all__ = ["EntityRecognitionService"]
