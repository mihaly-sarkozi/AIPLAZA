from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from .base import TenantSchemaBase
from .utils import _utcnow_naive


class KnowledgePiiMappingORM(TenantSchemaBase):
    __tablename__ = "knowledge_pii_mappings"
    __table_args__ = (
        UniqueConstraint("corpus_uuid", "entity_type", "entity_hash", name="uq_kpm_corpus_entity_hash"),
        UniqueConstraint("corpus_uuid", "token", name="uq_kpm_corpus_token"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    corpus_uuid = Column(String(36), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False, index=True)
    entity_hash = Column(String(64), nullable=False)
    token = Column(String(64), nullable=False)
    token_index = Column(Integer, nullable=False, default=0)
    encrypted_value = Column(String(4096), nullable=False)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False)
