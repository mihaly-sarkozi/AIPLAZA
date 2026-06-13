from __future__ import annotations

from apps.kb.kb_discovery.orm.DiscoveryJob import DiscoveryJob
from apps.kb.kb_discovery.orm.DiscoveryStepRun import DiscoveryStepRun
from apps.kb.kb_discovery.orm.EntityMention import EntityMention
from apps.kb.kb_discovery.orm.KnowledgeEnrichment import KnowledgeEnrichment
from apps.kb.kb_discovery.orm.KnowledgeEntity import KnowledgeEntity
from apps.kb.kb_discovery.orm.KnowledgeKeyword import KnowledgeKeyword
from apps.kb.kb_discovery.orm.KnowledgeRelationship import KnowledgeRelationship
from apps.kb.kb_discovery.orm.KnowledgeScore import KnowledgeScore
from apps.kb.kb_discovery.orm.KnowledgeTopic import KnowledgeTopic
from apps.kb.kb_discovery.orm.SpatialMention import SpatialMention
from apps.kb.kb_discovery.orm.TemporalMention import TemporalMention
from core.modules.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
)


def _install_kb_discovery_schema(engine, slug: str) -> None:
    install_schema_tables(
        engine,
        slug,
        (
            DiscoveryJob.__table__,
            DiscoveryStepRun.__table__,
            KnowledgeEntity.__table__,
            EntityMention.__table__,
            KnowledgeEnrichment.__table__,
            KnowledgeKeyword.__table__,
            KnowledgeTopic.__table__,
            TemporalMention.__table__,
            SpatialMention.__table__,
            KnowledgeRelationship.__table__,
            KnowledgeScore.__table__,
        ),
    )


def register_kb_discovery_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="kb_discovery",
                revision="kb.discovery.schema.v2",
                install=_install_kb_discovery_schema,
                table_names=(
                    "kb_discovery_jobs",
                    "kb_discovery_step_runs",
                    "kb_entities",
                    "kb_entity_mentions",
                    "kb_enrichments",
                    "kb_keywords",
                    "kb_topics",
                    "kb_temporal_mentions",
                    "kb_spatial_mentions",
                    "kb_relationships",
                    "kb_scores",
                ),
            )
        ]
    )


__all__ = ["register_kb_discovery_tenant_hooks"]
