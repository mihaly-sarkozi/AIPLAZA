from __future__ import annotations

# backend/apps/kb/kb_understanding/orm/UnderstandingStepRun.py
# Feladat: Egy pipeline-lépés futásának naplórekordja — a tesztelhetőségi szabály alapja
# (mit kapott, mit adott, mennyi ideig futott, hibázott-e).
# Sárközi Mihály - 2026.06.11

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class UnderstandingStepRun(TenantSchemaBase):
    __tablename__ = "kb_understanding_step_runs"

    # Egyedi futás azonosító (und_step_…).
    id = Column(String(64), primary_key=True)
    # Szülő job azonosító (kb_understanding_jobs.id).
    job_id = Column(String(64), nullable=False, index=True)
    # UnderstandingStep érték.
    step = Column(String(32), nullable=False, index=True)
    # Lépés kimeneti állapota: completed | failed | skipped.
    status = Column(String(32), nullable=False, default="completed", index=True)
    # Bemenet összegzése (méret, darabszám, hivatkozások) — nem a teljes tartalom.
    input_summary = Column(JSONB, nullable=False, default=dict)
    # Kimenet összegzése (darabszám, azonosítók, mérőszámok).
    output_summary = Column(JSONB, nullable=False, default=dict)
    # Futásidő ezredmásodpercben.
    duration_ms = Column(Integer, nullable=False, default=0)
    # Hibakód + részlet, ha a lépés hibázott.
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)


__all__ = ["UnderstandingStepRun"]
