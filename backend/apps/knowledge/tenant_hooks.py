# Ez a fájl a tenant-kezeléshez kapcsolódó egyik backend építőelemet tartalmazza.
from __future__ import annotations

from apps.knowledge.models import (
    KBORM,
    KbUserPermissionORM,
    KnowledgeClaimORM,
    KnowledgeDocumentORM,
    KnowledgeIngestEventORM,
    KnowledgeIngestInputORM,
    KnowledgeIngestItemORM,
    KnowledgeIngestRunORM,
    KnowledgeIndexBuildORM,
    KnowledgeInterpretationRunORM,
    KnowledgeMentionORM,
    KnowledgeParagraphORM,
    KnowledgeParserRunORM,
    KnowledgeQueryRunORM,
    KnowledgeSentenceORM,
    KnowledgeSentenceInterpretationORM,
    KnowledgeSpaceTimeFrameORM,
    KnowledgeSourceORM,
)
from apps.knowledge.repository.models.local_entity_cluster_orm import KnowledgeLocalEntityClusterORM
from apps.knowledge.service.knowledge_facade import KnowledgeFacade
from core.extensions.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
    run_schema_statements,
)
from core.extensions.tenant.slug.policy import initial_demo_knowledge_base_name
from core.platform.extensions.tenant_hooks import TenantSignupContext, register_tenant_signup_hook


# Ez a függvény telepíti a(z) knowledge séma logikáját.
def _install_knowledge_schema(engine, slug: str) -> None:
    install_schema_tables(
        engine,
        slug,
        (
            KBORM.__table__,
            KbUserPermissionORM.__table__,
            KnowledgeSourceORM.__table__,
            KnowledgeIngestRunORM.__table__,
            KnowledgeIngestItemORM.__table__,
            KnowledgeIngestInputORM.__table__,
            KnowledgeIngestEventORM.__table__,
            KnowledgeParserRunORM.__table__,
            KnowledgeDocumentORM.__table__,
            KnowledgeParagraphORM.__table__,
            KnowledgeSentenceORM.__table__,
            KnowledgeInterpretationRunORM.__table__,
            KnowledgeSentenceInterpretationORM.__table__,
            KnowledgeMentionORM.__table__,
            KnowledgeClaimORM.__table__,
            KnowledgeSpaceTimeFrameORM.__table__,
            KnowledgeLocalEntityClusterORM.__table__,
            KnowledgeIndexBuildORM.__table__,
            KnowledgeQueryRunORM.__table__,
        ),
    )
    run_schema_statements(
        engine,
        slug,
        (
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS created_by INTEGER',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS updated_by INTEGER',
            'ALTER TABLE "{schema}".kb_user_permission ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()',
            'ALTER TABLE "{schema}".kb_user_permission ADD COLUMN IF NOT EXISTS created_by INTEGER',
            'ALTER TABLE "{schema}".kb_user_permission ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()',
            'ALTER TABLE "{schema}".kb_user_permission ADD COLUMN IF NOT EXISTS updated_by INTEGER',
            'ALTER TABLE "{schema}".knowledge_local_entity_clusters ADD COLUMN IF NOT EXISTS explanation_json JSONB NOT NULL DEFAULT \'{{}}\'::jsonb',
        ),
    )


# Ez a függvény regisztrálja a(z) knowledge tenant hookok logikáját.
def register_knowledge_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="knowledge",
                revision="knowledge.interpretation.v4",
                install=_install_knowledge_schema,
                table_names=(
                    "knowledge_bases",
                    "kb_user_permission",
                    "knowledge_sources",
                    "knowledge_ingest_runs",
                    "knowledge_ingest_items",
                    "knowledge_ingest_inputs",
                    "knowledge_ingest_events",
                    "knowledge_parser_runs",
                    "knowledge_documents",
                    "knowledge_paragraphs",
                    "knowledge_sentences",
                    "knowledge_interpretation_runs",
                    "knowledge_sentence_interpretations",
                    "knowledge_mentions",
                    "knowledge_claims",
                    "knowledge_space_time_frames",
                    "knowledge_local_entity_clusters",
                    "knowledge_index_builds",
                    "knowledge_query_runs",
                ),
            )
        ]
    )


class KnowledgeTenantSignupHook:
    """Tenant signup hook: initial knowledge base bootstrap."""

    def __init__(self, knowledge_service: KnowledgeFacade) -> None:
        self._knowledge_service = knowledge_service

    def handle(self, context: TenantSignupContext) -> None:
        if self._knowledge_service.list_all_unfiltered():
            return
        self._knowledge_service.create(
            initial_demo_knowledge_base_name(context.locale),
            current_user_id=context.owner_id,
        )


def register_knowledge_tenant_signup_hook(knowledge_service: KnowledgeFacade) -> None:
    register_tenant_signup_hook(
        "knowledge",
        KnowledgeTenantSignupHook(knowledge_service),
    )
