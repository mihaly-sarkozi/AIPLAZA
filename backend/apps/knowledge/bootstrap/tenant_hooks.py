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
    KnowledgePiiMappingORM,
    KnowledgeQueryRunORM,
    KnowledgeSentenceInterpretationORM,
    KnowledgeSentenceORM,
    KnowledgeSourceORM,
    KnowledgeSpaceTimeFrameORM,
)
from apps.knowledge.repository.models.local_entity_cluster_orm import KnowledgeLocalEntityClusterORM
from apps.knowledge.service.knowledge_facade import KnowledgeFacade
from core.modules.tenant.extensions.tenant_hooks import TenantSignupContext, register_tenant_signup_hook
from core.modules.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
    run_schema_statements,
)
from core.modules.tenant.slug.policy import initial_demo_knowledge_base_name


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
            KnowledgePiiMappingORM.__table__,
        ),
    )
    run_schema_statements(
        engine,
        slug,
        (
            'ALTER TABLE "{schema}".knowledge_bases ALTER COLUMN name TYPE VARCHAR(200)',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS created_by INTEGER',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS updated_by INTEGER',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS deleted_display_name VARCHAR(200)',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS deleted_training_char_count BIGINT NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS pii_depersonalization_enabled BOOLEAN NOT NULL DEFAULT TRUE',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS public_enabled BOOLEAN NOT NULL DEFAULT FALSE',
            'ALTER TABLE "{schema}".kb_user_permission ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()',
            'ALTER TABLE "{schema}".kb_user_permission ADD COLUMN IF NOT EXISTS created_by INTEGER',
            'ALTER TABLE "{schema}".kb_user_permission ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()',
            'ALTER TABLE "{schema}".kb_user_permission ADD COLUMN IF NOT EXISTS updated_by INTEGER',
            'ALTER TABLE "{schema}".knowledge_ingest_items ADD COLUMN IF NOT EXISTS pipeline_version VARCHAR(64) NOT NULL DEFAULT \'source_parser.v1\'',
            'ALTER TABLE "{schema}".knowledge_ingest_items ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(192)',
            'ALTER TABLE "{schema}".knowledge_ingest_items ADD COLUMN IF NOT EXISTS lease_owner VARCHAR(128)',
            'ALTER TABLE "{schema}".knowledge_ingest_items ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMP',
            'ALTER TABLE "{schema}".knowledge_ingest_items ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMP',
            'ALTER TABLE "{schema}".knowledge_ingest_items ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".knowledge_ingest_items ADD COLUMN IF NOT EXISTS max_retries INTEGER NOT NULL DEFAULT 3',
            'ALTER TABLE "{schema}".knowledge_ingest_items ADD COLUMN IF NOT EXISTS dead_letter_reason VARCHAR(1024)',
            'CREATE INDEX IF NOT EXISTS ix_knowledge_ingest_items_worker_lease ON "{schema}".knowledge_ingest_items (status, lease_expires_at)',
            'CREATE INDEX IF NOT EXISTS ix_knowledge_ingest_items_idempotency ON "{schema}".knowledge_ingest_items (corpus_uuid, pipeline_version, content_hash)',
            'ALTER TABLE "{schema}".knowledge_local_entity_clusters ADD COLUMN IF NOT EXISTS explanation_json JSONB NOT NULL DEFAULT \'{{}}\'::jsonb',
        ),
    )


def _install_knowledge_fk_constraints(engine, slug: str) -> None:
    run_schema_statements(
        engine,
        slug,
        (
            """
            DO $$
            BEGIN
                IF to_regclass('"{schema}".knowledge_claims') IS NOT NULL
                   AND to_regclass('"{schema}".knowledge_sources') IS NOT NULL
                   AND NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'fk_knowledge_claims_source_id'
                      AND conrelid = to_regclass('"{schema}".knowledge_claims')
                ) THEN
                    ALTER TABLE "{schema}".knowledge_claims
                    ADD CONSTRAINT fk_knowledge_claims_source_id
                    FOREIGN KEY (source_id) REFERENCES "{schema}".knowledge_sources(id)
                    ON DELETE CASCADE NOT VALID;
                END IF;
            END $$;
            """,
            """
            DO $$
            BEGIN
                IF to_regclass('"{schema}".knowledge_claims') IS NOT NULL
                   AND to_regclass('"{schema}".knowledge_sentences') IS NOT NULL
                   AND NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'fk_knowledge_claims_sentence_id'
                      AND conrelid = to_regclass('"{schema}".knowledge_claims')
                ) THEN
                    ALTER TABLE "{schema}".knowledge_claims
                    ADD CONSTRAINT fk_knowledge_claims_sentence_id
                    FOREIGN KEY (sentence_id) REFERENCES "{schema}".knowledge_sentences(id)
                    ON DELETE CASCADE NOT VALID;
                END IF;
            END $$;
            """,
            """
            DO $$
            BEGIN
                IF to_regclass('"{schema}".knowledge_mentions') IS NOT NULL
                   AND to_regclass('"{schema}".knowledge_sentences') IS NOT NULL
                   AND NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'fk_knowledge_mentions_sentence_id'
                      AND conrelid = to_regclass('"{schema}".knowledge_mentions')
                ) THEN
                    ALTER TABLE "{schema}".knowledge_mentions
                    ADD CONSTRAINT fk_knowledge_mentions_sentence_id
                    FOREIGN KEY (sentence_id) REFERENCES "{schema}".knowledge_sentences(id)
                    ON DELETE CASCADE NOT VALID;
                END IF;
            END $$;
            """,
            """
            DO $$
            BEGIN
                IF to_regclass('"{schema}".knowledge_space_time_frames') IS NOT NULL
                   AND to_regclass('"{schema}".knowledge_claims') IS NOT NULL
                   AND NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'fk_knowledge_space_time_frames_claim_id'
                      AND conrelid = to_regclass('"{schema}".knowledge_space_time_frames')
                ) THEN
                    ALTER TABLE "{schema}".knowledge_space_time_frames
                    ADD CONSTRAINT fk_knowledge_space_time_frames_claim_id
                    FOREIGN KEY (claim_id) REFERENCES "{schema}".knowledge_claims(id)
                    ON DELETE CASCADE NOT VALID;
                END IF;
            END $$;
            """,
            """
            DO $$
            BEGIN
                IF to_regclass('"{schema}".knowledge_space_time_frames') IS NOT NULL
                   AND to_regclass('"{schema}".knowledge_sentences') IS NOT NULL
                   AND NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'fk_knowledge_space_time_frames_sentence_id'
                      AND conrelid = to_regclass('"{schema}".knowledge_space_time_frames')
                ) THEN
                    ALTER TABLE "{schema}".knowledge_space_time_frames
                    ADD CONSTRAINT fk_knowledge_space_time_frames_sentence_id
                    FOREIGN KEY (sentence_id) REFERENCES "{schema}".knowledge_sentences(id)
                    ON DELETE CASCADE NOT VALID;
                END IF;
            END $$;
            """,
            """
            DO $$
            BEGIN
                IF to_regclass('"{schema}".knowledge_space_time_frames') IS NOT NULL
                   AND to_regclass('"{schema}".knowledge_sources') IS NOT NULL
                   AND NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'fk_knowledge_space_time_frames_source_id'
                      AND conrelid = to_regclass('"{schema}".knowledge_space_time_frames')
                ) THEN
                    ALTER TABLE "{schema}".knowledge_space_time_frames
                    ADD CONSTRAINT fk_knowledge_space_time_frames_source_id
                    FOREIGN KEY (source_id) REFERENCES "{schema}".knowledge_sources(id)
                    ON DELETE CASCADE NOT VALID;
                END IF;
            END $$;
            """,
        ),
    )


def register_knowledge_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="knowledge",
                revision="knowledge.schema.worker_first_ingest.v6.kb_visibility_flags",
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
                    "knowledge_pii_mappings",
                ),
            ),
            TenantSchemaHook(
                name="knowledge_fk_constraints",
                revision="knowledge.schema.worker_first_ingest.v5.referential_integrity",
                install=_install_knowledge_fk_constraints,
            ),
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

__all__ = [
    "KnowledgeTenantSignupHook",
    "register_knowledge_tenant_hooks",
    "register_knowledge_tenant_signup_hook",
]
