# backend/core/kernel/events/outbox.py
# Feladat: A platform event outbox repository publikus műveleteit tartalmazza: append, backlog mérés, batch claim, processed/failed állapotkezelés. A web process ide írja az eseményeket, a worker pedig innen veszi át őket SKIP LOCKED kompatibilis módon. Core perzisztens eseménysor, amely több processzes deploymentben is használható.
# Sárközi Mihály - 2026.05.21

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
from datetime import timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from core.kernel.runtime.clock import utc_now
from core.kernel.events.outbox_models import OutboxWorkItem, PlatformEventOutboxORM
from core.kernel.events.outbox_queries import (
    mark_claimed,
    outbox_eligible_filter,
    to_work_item,
)
from core.kernel.events.outbox_sql import (
    install_platform_event_outbox,
    upgrade_platform_event_outbox_schema,
)


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

    def claim(
        self,
        *,
        limit: int = 100,
        stale_lock_after_sec: int = 300,
        lease_seconds: int = 300,
        lock_owner: str | None = None,
    ) -> list[OutboxWorkItem]:
        return self.claim_next_batch(
            limit=limit,
            stale_lock_after_sec=stale_lock_after_sec,
            lease_seconds=lease_seconds,
            lock_owner=lock_owner,
        )

    def ack(self, event_id: int) -> None:
        self.mark_processed(event_id)

    def fail(self, event_id: int, *, error: str, max_attempts: int, retry_delay_seconds: int) -> None:
        self.mark_failed(
            event_id,
            error=error,
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay_seconds,
        )

    def retry(self, event_id: int, *, error: str, retry_delay_seconds: int) -> None:
        self.mark_failed(
            event_id,
            error=error,
            max_attempts=10**9,
            retry_delay_seconds=retry_delay_seconds,
        )

    def dead_letter(self, event_id: int, *, error: str) -> None:
        with self._sf() as db:
            row = db.get(PlatformEventOutboxORM, event_id)
            if row is None:
                return
            now = utc_now()
            row.attempts = int(row.attempts or 0) + 1
            row.last_error = error[:4000]
            row.status = "dead_letter"
            row.updated_at = now
            row.finished_at = now
            row.locked_at = None
            row.lock_owner = None
            row.leased_by = None
            row.lease_until = None
            db.commit()

    def backlog_size(self) -> int:
        """Aktuális feldolgozatlan backlog méret (pending/retry/processing)."""
        with self._sf() as db:
            count = (
                db.query(func.count(PlatformEventOutboxORM.id))
                .filter(PlatformEventOutboxORM.status.in_(("pending", "retry", "processing")))
                .scalar()
                or 0
            )
            return int(count)

    def queue_snapshot(self) -> dict[str, Any]:
        with self._sf() as db:
            now = utc_now()
            status_rows = (
                db.query(PlatformEventOutboxORM.status, func.count(PlatformEventOutboxORM.id))
                .group_by(PlatformEventOutboxORM.status)
                .all()
            )
            oldest_pending = (
                db.query(func.min(PlatformEventOutboxORM.created_at))
                .filter(PlatformEventOutboxORM.status.in_(("pending", "retry")))
                .scalar()
            )
            stuck_leases = (
                db.query(func.count(PlatformEventOutboxORM.id))
                .filter(
                    PlatformEventOutboxORM.status == "processing",
                    PlatformEventOutboxORM.lease_until.isnot(None),
                    PlatformEventOutboxORM.lease_until < now,
                )
                .scalar()
                or 0
            )
            latest_heartbeat = (
                db.query(func.max(PlatformEventOutboxORM.last_heartbeat_at))
                .filter(
                    PlatformEventOutboxORM.status == "processing",
                    PlatformEventOutboxORM.last_heartbeat_at.isnot(None),
                )
                .scalar()
            )
            avg_attempts = db.query(func.avg(PlatformEventOutboxORM.attempts)).scalar() or 0
            return {
                "by_status": {str(status): int(count or 0) for status, count in status_rows},
                "pending_jobs": _status_count(status_rows, "pending") + _status_count(status_rows, "retry"),
                "running_jobs": _status_count(status_rows, "processing"),
                "failed_jobs": _status_count(status_rows, "failed"),
                "dead_letter_jobs": _status_count(status_rows, "dead_letter"),
                "oldest_pending_age_seconds": (
                    max(0.0, (now - oldest_pending).total_seconds()) if oldest_pending is not None else 0.0
                ),
                "stuck_leases": int(stuck_leases),
                "average_attempt_count": float(avg_attempts),
                "worker_heartbeat_at": latest_heartbeat.isoformat() if latest_heartbeat is not None else None,
                "worker_heartbeat_age_seconds": (
                    max(0.0, (now - latest_heartbeat).total_seconds()) if latest_heartbeat is not None else None
                ),
            }

    def claim_next_batch(
        self,
        *,
        limit: int = 100,
        stale_lock_after_sec: int = 300,
        lease_seconds: int = 300,
        lock_owner: str | None = None,
    ) -> list[OutboxWorkItem]:
        """Atomikusan lefoglalja a következő feldolgozandó sorokat (SKIP LOCKED).

        - pending/retry + esedékes next_retry_at
        - vagy processing, de locked_at régebbi mint (most - stale_lock_after_sec)
        """
        now = utc_now()
        stale_before = now - timedelta(seconds=max(1, int(stale_lock_after_sec)))
        lease_until = now + timedelta(seconds=max(1, int(lease_seconds)))
        owner = (lock_owner or "").strip() or None

        eligible = outbox_eligible_filter(now=now, stale_before=stale_before)

        with self._sf() as db:
            rows = (
                db.query(PlatformEventOutboxORM)
                .filter(eligible)
                .order_by(PlatformEventOutboxORM.id.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
                .all()
            )
            snapshots = [to_work_item(r) for r in rows]
            for row in rows:
                mark_claimed(row, now=now, lock_owner=owner, lease_until=lease_until)
            db.commit()
        return snapshots

    def heartbeat(self, event_id: int, *, lock_owner: str | None, lease_seconds: int) -> None:
        with self._sf() as db:
            row = db.get(PlatformEventOutboxORM, event_id)
            if row is None or row.status != "processing":
                return
            owner = (lock_owner or "").strip() or None
            if owner and row.leased_by and row.leased_by != owner:
                return
            now = utc_now()
            row.last_heartbeat_at = now
            row.lease_until = now + timedelta(seconds=max(1, int(lease_seconds)))
            row.updated_at = now
            db.commit()

    def mark_processed(self, event_id: int) -> None:
        with self._sf() as db:
            row = db.get(PlatformEventOutboxORM, event_id)
            if row is None:
                return
            row.status = "processed"
            row.processed_at = utc_now()
            row.finished_at = row.processed_at
            row.updated_at = row.processed_at
            row.last_error = None
            row.locked_at = None
            row.lock_owner = None
            row.leased_by = None
            row.lease_until = None
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
            row.leased_by = None
            row.lease_until = None
            if row.attempts >= max_attempts:
                row.status = "dead_letter"
                row.finished_at = utc_now()
            else:
                row.status = "retry"
                delay = max(1, retry_delay_seconds) * row.attempts
                row.next_retry_at = utc_now() + timedelta(seconds=delay)
            db.commit()


class IdempotencyService:
    def __init__(self, repository: PlatformEventOutboxRepository) -> None:
        self._repository = repository

    def publish_once(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> PlatformEventOutboxORM:
        key = str(idempotency_key or "").strip()
        if not key:
            raise ValueError("idempotency_key is required")
        return self._repository.append(event_type=event_type, payload=payload, idempotency_key=key)


class OutboxHealthService:
    def __init__(self, repository: PlatformEventOutboxRepository) -> None:
        self._repository = repository

    def queue_snapshot(self) -> dict[str, Any]:
        return self._repository.queue_snapshot()


def _status_count(rows: list[tuple[Any, Any]], status_name: str) -> int:
    for status, count in rows:
        if str(status) == status_name:
            return int(count or 0)
    return 0


def ensure_platform_event_outbox(engine) -> None:
    with engine.connect() as conn:
        install_platform_event_outbox(conn)
        upgrade_platform_event_outbox_schema(conn)
        commit = getattr(conn, "commit", None)
        if callable(commit):
            commit()


__all__ = [
    "IdempotencyService",
    "OutboxWorkItem",
    "OutboxHealthService",
    "PlatformEventOutboxORM",
    "PlatformEventOutboxRepository",
    "ensure_platform_event_outbox",
]
