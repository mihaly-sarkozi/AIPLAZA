# backend/core/kernel/events/outbox_queries.py
# Feladat: Az outbox repository query helper logikáját különíti el. Meghatározza, mely sorok feldolgozhatók, hogyan készül belőlük worker snapshot, és hogyan jelöljük őket claimelt állapotba. Belső core helper, amely az outbox.py méretét és felelősségét tartja tisztán.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, or_

from core.kernel.events.outbox_models import OutboxWorkItem, PlatformEventOutboxORM


def outbox_eligible_filter(*, now: datetime, stale_before: datetime):
    return or_(
        and_(
            PlatformEventOutboxORM.status.in_(("pending", "retry")),
            PlatformEventOutboxORM.next_retry_at <= now,
        ),
        and_(
            PlatformEventOutboxORM.status == "processing",
            or_(
                PlatformEventOutboxORM.lease_until.isnot(None)
                & (PlatformEventOutboxORM.lease_until < now),
                PlatformEventOutboxORM.locked_at.isnot(None)
                & (PlatformEventOutboxORM.locked_at < stale_before),
            ),
        ),
    )


def to_work_item(row: PlatformEventOutboxORM) -> OutboxWorkItem:
    return OutboxWorkItem(
        id=row.id,
        event_type=row.event_type,
        payload=dict(row.payload or {}),
        attempts=int(row.attempts or 0),
        lease_until=row.lease_until,
    )


def mark_claimed(row: PlatformEventOutboxORM, *, now: datetime, lock_owner: str | None, lease_until: datetime | None = None) -> None:
    row.status = "processing"
    row.locked_at = now
    row.lock_owner = lock_owner
    row.leased_by = lock_owner
    row.lease_until = lease_until
    row.last_heartbeat_at = now
    row.started_at = row.started_at or now
    row.updated_at = now


__all__ = [
    "mark_claimed",
    "outbox_eligible_filter",
    "to_work_item",
]
