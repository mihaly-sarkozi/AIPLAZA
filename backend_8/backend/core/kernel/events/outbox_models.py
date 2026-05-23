# backend/core/kernel/events/outbox_models.py
# Feladat: Az outbox tábla ORM modelljét és a workernek átadott immutable work item snapshotot definiálja. A repository ezekkel dolgozik, így a worker session lezárása után is biztonságosan feldolgozhatja az eseményeket. Core adatmodell az event outbox infrastruktúrához.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.kernel.runtime.clock import utc_now
from core.kernel.db.model_bases import PublicBase


@dataclass(frozen=True)
class OutboxWorkItem:
    """Worker számára snapshot egy outbox sorról (session-lezárás után is biztonságos)."""

    id: int
    event_type: str
    payload: dict[str, Any]
    attempts: int = 0
    lease_until: datetime | None = None


class PlatformEventOutboxORM(PublicBase):
    __tablename__ = "platform_event_outbox"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lock_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    leased_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["OutboxWorkItem", "PlatformEventOutboxORM"]
