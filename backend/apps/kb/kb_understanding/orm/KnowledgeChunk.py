from __future__ import annotations

# backend/apps/kb/kb_understanding/orm/KnowledgeChunk.py
# Feladat: Kereshető tudás-chunk a kötelező bizonyíték-metaadatokkal (chunking kimenete).
# Sárközi Mihály - 2026.06.11

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class KnowledgeChunk(TenantSchemaBase):
    """Bizonyíték szabály: minden chunk visszavezethető az eredeti forrásra."""

    __tablename__ = "kb_chunks"

    # Egyedi chunk azonosító (chunk_…).
    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    # Forrás dokumentum = ingest item.
    document_id = Column(String(64), nullable=False, index=True)
    # Forrás azonosító (raw_ref object storage kulcs).
    source_id = Column(String(1024), nullable=False, default="")
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    # Eredeti fájlnév (ha fájl-alapú a forrás).
    file_name = Column(String(255), nullable=True)
    # Forrás típusa: text | file | url.
    source_type = Column(String(16), nullable=False, default="text")
    # A chunk szövegének SHA-256 hash-e.
    checksum = Column(String(128), nullable=False, default="", index=True)
    # Feldolgozási verzió (újrafuttatásnál nő).
    version = Column(Integer, nullable=False, default=1)
    # Forráshely.
    page_number = Column(Integer, nullable=True)
    section_title = Column(String(512), nullable=True)
    # Sorrend a dokumentumon belül.
    order_index = Column(Integer, nullable=False, default=0, index=True)
    # ChunkType érték.
    chunk_type = Column(String(32), nullable=False, default="text", index=True)
    text = Column(Text, nullable=False, default="")
    # Becsült token szám.
    token_count = Column(Integer, nullable=False, default=0)
    # Chunk szintű nyelvdetektálás (discovery állítja be).
    language_code = Column(String(16), nullable=True, index=True)
    language_confidence = Column(Float, nullable=True)
    language_detected_by = Column(String(64), nullable=True)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    last_processed_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)
    # Kiegészítő meta.
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)


__all__ = ["KnowledgeChunk"]
