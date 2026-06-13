from __future__ import annotations

from typing import Any

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import EntityMentionDto, KnowledgeEntityDto
from apps.kb.kb_discovery.entities.EntityRecognitionService import EntityRecognitionService
from apps.kb.kb_discovery.persons.PersonDirectoryProvider import PersonDirectoryProvider
from apps.kb.kb_discovery.persons.PersonRecognitionService import PersonRecognitionService
from apps.kb.kb_discovery.repository.EntityRepository import EntityMentionRepository, EntityRepository
from apps.kb.kb_processing.enums.ProcessingIssueCode import ProcessingIssueCode
from apps.kb.kb_processing.enums.ProcessingIssueSeverity import ProcessingIssueSeverity
from apps.kb.shared.ports.processing_flow_recorder import (
    NoOpProcessingFlowRecorder,
    ProcessingFlowContext,
    ProcessingFlowRecorder,
)


class ExtractEntitiesService:
    def __init__(
        self,
        entity_repository: EntityRepository,
        mention_repository: EntityMentionRepository,
        *,
        person_directory=None,
        flow_recorder: ProcessingFlowRecorder | None = None,
    ) -> None:
        directory_provider = PersonDirectoryProvider(person_directory or [])
        self._person = PersonRecognitionService(
            entity_repository,
            mention_repository,
            directory_provider=directory_provider,
        )
        self._entity = EntityRecognitionService(entity_repository, mention_repository)
        self._flow_recorder = flow_recorder or NoOpProcessingFlowRecorder()

    def run(
        self,
        ctx: DiscoveryJobContext,
        chunks: list[DiscoveryChunkDto],
    ) -> tuple[list[KnowledgeEntityDto], list[EntityMentionDto]]:
        person_entities, person_mentions = self._person.run(ctx, chunks)
        entities, mentions, dictionary_warnings = self._entity.run(
            ctx,
            chunks,
            person_entities=person_entities,
            person_mentions=person_mentions,
        )
        self._report_dictionary_warnings(ctx, dictionary_warnings)
        return entities, mentions

    def _report_dictionary_warnings(
        self,
        ctx: DiscoveryJobContext,
        warnings: list[dict[str, Any]],
    ) -> None:
        if not warnings:
            return
        flow_ctx = ProcessingFlowContext(
            tenant_slug=ctx.tenant_slug or "",
            knowledge_base_id=ctx.knowledge_base_id,
            training_batch_id=ctx.training_batch_id,
            training_item_id=ctx.training_item_id,
            job_id=ctx.job_id,
            created_by=ctx.created_by,
        )
        for warning in warnings:
            self._flow_recorder.open_issue(
                flow_ctx,
                module="kb_discovery",
                stage="entity_extraction",
                step="dictionary_entity",
                severity=ProcessingIssueSeverity.WARNING.value,
                issue_code=ProcessingIssueCode.INVALID_ENTITY_DICTIONARY_TYPE.value,
                issue_message=(
                    f"Invalid entity dictionary type '{warning.get('invalid_type')}' "
                    f"for entry '{warning.get('entry_name')}'"
                ),
                metadata_json=warning,
            )


__all__ = ["ExtractEntitiesService"]
