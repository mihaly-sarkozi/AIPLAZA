"""Platform esemény outbox – perzisztens sor, több workerrel kompatibilis claim.

Több példány / horizontális skálázás:
  - ``claim_next_batch`` egy tranzakcióban ``FOR UPDATE SKIP LOCKED``-dal foglal
    sorokat, így két worker nem veheti ugyanazt az eseményt.
  - ``locked_at`` + lejárt lock: összeomlott worker után a sor újra claimelhető.
  - Opcionális ``idempotency_key``: ugyanazzal a kulccsal történő ``append``
    duplikált sort nem hoz létre (deduplikáció publish szinten).

A web kérések csak ``append``-et hívnak; a feldolgozás külön folyamatban / workerben
történik (``OutboxWorker``).
"""
from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, and_, func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from core.kernel.clock import utc_now
from core.kernel.db.model_bases import PublicBase


@dataclass(frozen=True)
class OutboxWorkItem:
    """Worker számára snapshot egy outbox sorról (session-lezárás után is biztonságos)."""

    id: int
    event_type: str
    payload: dict[str, Any]
    attempts: int = 0


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


class PlatformEventOutboxRepository:
    def __init__(self, session_factory: Callable[[], AbstractContextManager[Any]]):
        self._sf = session_factory

    def append(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> PlatformEventOutboxORM:
        """Új esemény beszúrása. Azonos nem üres idempotency_key esetén a már meglévő sor."""
        key = (idempotency_key or "").strip() or None
        clean_payload = json.loads(json.dumps(payload, ensure_ascii=False))
        with self._sf() as db:
            if key:
                existing = (
                    db.query(PlatformEventOutboxORM)
                    .filter(PlatformEventOutboxORM.idempotency_key == key)
                    .first()
                )
                if existing is not None:
                    return existing
            row = PlatformEventOutboxORM(
                event_type=event_type,
                payload=clean_payload,
                status="pending",
                attempts=0,
                last_error=None,
                next_retry_at=utc_now(),
                idempotency_key=key,
                locked_at=None,
                lock_owner=None,
            )
            db.add(row)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                if key:
                    existing = (
                        db.query(PlatformEventOutboxORM)
                        .filter(PlatformEventOutboxORM.idempotency_key == key)
                        .first()
                    )
                    if existing is not None:
                        return existing
                raise
            db.refresh(row)
            return row

    def claim_next_batch(
        self,
        *,
        limit: int = 100,
        stale_lock_after_sec: int = 300,
        lock_owner: str | None = None,
    ) -> list[OutboxWorkItem]:
        """Atomikusan lefoglalja a következő feldolgozandó sorokat (SKIP LOCKED).

        - pending/retry + esedékes next_retry_at
        - vagy processing, de locked_at régebbi mint (most - stale_lock_after_sec)
        """
        now = utc_now()
        stale_before = now - timedelta(seconds=max(1, int(stale_lock_after_sec)))
        owner = (lock_owner or "").strip() or None

        eligible = or_(
            and_(
                PlatformEventOutboxORM.status.in_(("pending", "retry")),
                PlatformEventOutboxORM.next_retry_at <= now,
            ),
            and_(
                PlatformEventOutboxORM.status == "processing",
                PlatformEventOutboxORM.locked_at.isnot(None),
                PlatformEventOutboxORM.locked_at < stale_before,
            ),
        )

        with self._sf() as db:
            rows = (
                db.query(PlatformEventOutboxORM)
                .filter(eligible)
                .order_by(PlatformEventOutboxORM.id.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
                .all()
            )
            snapshots = [
                OutboxWorkItem(
                    id=r.id,
                    event_type=r.event_type,
                    payload=dict(r.payload or {}),
                    attempts=int(r.attempts or 0),
                )
                for r in rows
            ]
            for r in rows:
                r.status = "processing"
                r.locked_at = now
                r.lock_owner = owner
                r.updated_at = now
            db.commit()
        return snapshots

    def mark_processed(self, event_id: int) -> None:
        with self._sf() as db:
            row = db.get(PlatformEventOutboxORM, event_id)
            if row is None:
                return
            row.status = "processed"
            row.processed_at = utc_now()
            row.updated_at = utc_now()
            row.last_error = None
            row.locked_at = None
            row.lock_owner = None
            db.commit()

    def mark_failed(
        self,
        event_id: int,
        *,
        error: str,
        max_attempts: int,
        retry_delay_seconds: int,
    ) -> None:
        with self._sf() as db:
            row = db.get(PlatformEventOutboxORM, event_id)
            if row is None:
                return
            row.attempts = int(row.attempts or 0) + 1
            row.last_error = error[:4000]
            row.updated_at = utc_now()
            row.locked_at = None
            row.lock_owner = None
            if row.attempts >= max_attempts:
                row.status = "failed"
            else:
                row.status = "retry"
                delay = max(1, retry_delay_seconds) * row.attempts
                row.next_retry_at = utc_now() + timedelta(seconds=delay)
            db.commit()


def _install_platform_event_outbox(conn) -> None:
    conn.execute(
        text(
            """
        CREATE TABLE IF NOT EXISTS public.platform_event_outbox (
            id SERIAL PRIMARY KEY,
            event_type VARCHAR(64) NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            status VARCHAR(16) NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT NULL,
            next_retry_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            processed_at TIMESTAMPTZ NULL,
            idempotency_key VARCHAR(128) NULL,
            locked_at TIMESTAMPTZ NULL,
            lock_owner VARCHAR(128) NULL
        )
        """
        )
    )
    conn.execute(
        text(
            """
        CREATE INDEX IF NOT EXISTS ix_platform_event_outbox_status_retry
        ON public.platform_event_outbox (status, next_retry_at)
        """
        )
    )
    conn.execute(
        text(
            """
        CREATE INDEX IF NOT EXISTS ix_platform_event_outbox_type_status
        ON public.platform_event_outbox (event_type, status)
        """
        )
    )


def _upgrade_platform_event_outbox_schema(conn) -> None:
    """Meglévő táblákra: oszlopok és indexek, ha hiányoznak (indításkor idempotens)."""
    stmts = [
        "ALTER TABLE public.platform_event_outbox ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128) NULL",
        "ALTER TABLE public.platform_event_outbox ADD COLUMN IF NOT EXISTS locked_at TIMESTAMPTZ NULL",
        "ALTER TABLE public.platform_event_outbox ADD COLUMN IF NOT EXISTS lock_owner VARCHAR(128) NULL",
    ]
    for s in stmts:
        conn.execute(text(s))
    conn.execute(
        text(
            """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_platform_event_outbox_idempotency_key_unique
        ON public.platform_event_outbox (idempotency_key)
        WHERE idempotency_key IS NOT NULL
        """
        )
    )
    conn.execute(
        text(
            """
        CREATE INDEX IF NOT EXISTS ix_platform_event_outbox_stale_lock
        ON public.platform_event_outbox (status, locked_at)
        WHERE status = 'processing'
        """
        )
    )


def ensure_platform_event_outbox(engine) -> None:
    with engine.connect() as conn:
        _install_platform_event_outbox(conn)
        _upgrade_platform_event_outbox_schema(conn)
        commit = getattr(conn, "commit", None)
        if callable(commit):
            commit()


__all__ = [
    "OutboxWorkItem",
    "PlatformEventOutboxORM",
    "PlatformEventOutboxRepository",
    "ensure_platform_event_outbox",
]
