from __future__ import annotations

# backend/apps/kb/kb_understanding/orm/UnderstandingJob.py
# Feladat: Egy ingest itemhez tartozó megértési feldolgozás (job) állapotrekordja.
# Sárközi Mihály - 2026.06.11

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class UnderstandingJob(TenantSchemaBase):
    """A pipeline futás fő rekordja — státusz, hiba, retry, időbélyegek."""

    __tablename__ = "kb_understanding_jobs"

    # Egyedi job azonosító (und_job_…).
    id = Column(String(64), primary_key=True)
    # Forrás ingest item azonosító (kb_ingest_items.id).
    training_item_id = Column(String(64), nullable=False, index=True)
    # Forrás ingest batch azonosító.
    training_batch_id = Column(String(64), nullable=False, index=True)
    # Cél tudástár UUID.
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    # UnderstandingStatus érték.
    status = Column(String(32), nullable=False, default="created", index=True)
    # Gépi hibakód (UnderstandingErrorCode).
    error_code = Column(String(64), nullable=True)
    # Technikai hiba részlet (log / debug).
    error_message = Column(Text, nullable=True)
    # Újrapróbálható-e a feldolgozás.
    retryable = Column(Boolean, nullable=False, default=False)
    # Eddigi újrapróbálások száma.
    retry_count = Column(Integer, nullable=False, default=0)
    # Indító felhasználó (ingest created_by).
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)
    # Kiegészítő meta (pl. forrás mime, char_count).
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)


__all__ = ["UnderstandingJob"]
