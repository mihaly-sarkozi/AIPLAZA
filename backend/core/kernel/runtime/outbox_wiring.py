# backend/core/kernel/runtime/outbox_wiring.py
# Feladat: Security registryből és outbox repositoryból OutboxWorker példányt állít össze. Settings alapján adja át a stale lock, handler timeout, retry és poll konfigurációt, és csak akkor hoz létre workert, ha az event channel engedélyezett. Core runtime wiring az async audit/event pipeline indításához.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.config.config_loader import settings
from core.kernel.bootstrap.security import SecurityRegistry
from core.kernel.events.outbox import PlatformEventOutboxRepository
from core.kernel.events.worker import OutboxWorker, default_outbox_lock_owner


def wire_outbox_worker(
    event_outbox_repo: PlatformEventOutboxRepository,
    security: SecurityRegistry,
) -> OutboxWorker | None:
    """OutboxWorker példány, ha az async audit pipeline be van kapcsolva."""
    channel = security.event_channel
    if channel is None:
        return None
    stale = max(1, int(getattr(settings, "platform_event_outbox_stale_lock_sec", 300)))
    lease = max(1, int(getattr(settings, "platform_event_outbox_lease_sec", 300)))
    handler_timeout = max(1, int(getattr(settings, "platform_event_handler_timeout_sec", 15)))
    return OutboxWorker(
        event_outbox_repo,
        security.dispatcher,
        poll_interval_seconds=channel.poll_interval_seconds,
        max_retries=channel.max_retries,
        retry_delay_seconds=channel.retry_delay_seconds,
        stale_lock_after_sec=stale,
        handler_timeout_seconds=handler_timeout,
        lease_seconds=lease,
        lock_owner=default_outbox_lock_owner(),
    )

