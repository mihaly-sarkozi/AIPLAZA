from __future__ import annotations

# backend/apps/kb/kb_ingest/orm/TrainingEvent.py
# Feladat: Tanítási folyamat eseménynapló (audit / timeline) perzisztencia.
# Sárközi Mihály - 2026.06.07

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from shared.utils.clock import utc_now_naive
from core.kernel.db.model_bases import TenantSchemaBase


class TrainingEvent(TenantSchemaBase):
    """Batch vagy item szintű esemény a tanítási naplóban.

    Az ``event_type`` gépi kód (pl. ``training_batch_created`` — lásd ``TrainingAuditEventType``);
    a ``message`` mező üresen hagyható, a megjelenítés az eseménytípus + ``details`` alapján
    történik. A ``details_json`` strukturált, nyelvfüggetlen meta (azonosítók, számlálók).
    """

    __tablename__ = "kb_ingest_events"

    # Egyedi esemény azonosító (pl. training_event_…).
    id = Column(String(64), primary_key=True)
    # Melyik batch-hez tartozik az esemény.
    training_batch_id = Column(String(64), nullable=False, index=True)
    # Ha item-specifikus esemény: az item ``id``-ja; batch-szintű eseménynél ``None``.
    training_item_id = Column(String(64), nullable=True, index=True)
    # Gépi eseménytípus kód (nem lokalizált szöveg).
    event_type = Column(String(64), nullable=False, index=True)
    # Opcionális rövid megjegyzés; preferált: üres, a kliens az ``event_type``-ból fordít.
    message = Column(Text, nullable=False, default="")
    # Strukturált részletek (pl. ``raw_ref``, ``status``, ``accepted_count``).
    details_json = Column("details", JSONB, nullable=False, default=dict)
    # Esemény időbélyege (UTC, naive).
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)


__all__ = ["TrainingEvent"]
