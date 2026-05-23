# Megjegyzés: nincs Alembic; új táblák tenantonként a tenant hook-on keresztül jönnek létre
# (lásd apps/knowledge/tenant_hooks.py). Meglévő telepítésekhez a séma revision léptetése szükséges.
from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from apps.knowledge.models.base import TenantSchemaBase
from apps.knowledge.models.utils import _utcnow_naive


class KnowledgeLocalEntityClusterORM(TenantSchemaBase):
    __tablename__ = "knowledge_local_entity_clusters"

    local_entity_id = Column(PG_UUID(as_uuid=True), primary_key=True)
    run_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)
    source_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)
    canonical_name = Column(Text, nullable=False, default="", index=True)
    entity_type = Column(String(64), nullable=False, default="unknown", index=True)
    normalized_key = Column(Text, nullable=False, default="", index=True)
    mention_ids = Column(JSONB, nullable=False, default=list)
    claim_ids = Column(JSONB, nullable=False, default=list)
    sentence_ids = Column(JSONB, nullable=False, default=list)
    surface_forms = Column(JSONB, nullable=False, default=list)
    evidence_refs = Column(JSONB, nullable=False, default=list)
    confidence = Column(Float, nullable=False, default=0.0)
    coherence_score = Column(Float, nullable=False, default=0.0)
    resolver_version = Column(String(64), nullable=False, default="local_resolver_v1")
    explanation_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)


__all__ = ["KnowledgeLocalEntityClusterORM"]
