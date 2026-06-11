from __future__ import annotations

# backend/apps/kb/kb_ingest/orm/TrainingBatch.py
# Feladat: Tanítási köteg (batch) perzisztencia — egy API hívás / feltöltési művelet összesítő rekordja.
# Sárközi Mihály - 2026.06.07

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from shared.utils.clock import utc_now_naive
from core.kernel.db.model_bases import TenantSchemaBase


class TrainingBatch(TenantSchemaBase):
    """Egy tanítási futás metaadata és összesítő számlálói.

    Egy batch több ``TrainingItem`` rekordot fog össze (jelenleg szöveges tanításnál
    tipikusan 1 item). A státusz és számlálók a batch szintű előrehaladást írják le;
    az egyes elemek állapota a ``kb_ingest_items`` táblában van.
    """

    __tablename__ = "kb_ingest_batches"

    # Egyedi batch azonosító (pl. training_batch_…).
    id = Column(String(64), primary_key=True)
    # Tenant slug — melyik bérlő sémában futott a tanítás.
    tenant = Column(String(128), nullable=False, index=True)
    # Cél tudástár UUID-ja.
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    # Bemeneti csatorna kódja: pl. ``text`` (később file, url).
    input_channel = Column(String(32), nullable=False, default="text")
    # Batch életciklus: ``pending`` | ``running`` | ``completed`` | ``partial_success`` | ``failed``.
    status = Column(String(32), nullable=False, default="pending", index=True)
    # A batchben lévő / várt elemek száma.
    batch_size = Column(Integer, nullable=False, default=0)
    # Feldolgozásra váró (elfogadott) elemek száma.
    queued_count = Column(Integer, nullable=False, default=0)
    # Véglegesen sikertelen elemek száma.
    failed_count = Column(Integer, nullable=False, default=0)
    # Szabály miatt elutasított elemek száma.
    rejected_count = Column(Integer, nullable=False, default=0)
    # Duplikátumként felismert elemek száma.
    duplicate_count = Column(Integer, nullable=False, default=0)
    # A tanítást indító platform felhasználó azonosítója.
    created_by = Column(Integer, nullable=False)
    # Batch létrehozásának ideje (UTC, naive).
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    # Batch lezárásának ideje; futó batch-nél ``None``.
    completed_at = Column(DateTime, nullable=True)
    # Utolsó módosítás ideje.
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)
    # Kiegészítő, strukturált meta (pl. ``input_types``, pipeline verzió) — nem lokalizált szöveg.
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)


__all__ = ["TrainingBatch"]
