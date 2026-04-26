"""Event / outbox wiring: OutboxWorker összerakása a dispatcherrel és az outbox repo-val."""
from __future__ import annotations

from core.kernel.config.config_loader import settings
from core.platform.bootstrap.security import SecurityRegistry
from core.platform.events.outbox import PlatformEventOutboxRepository
from core.platform.events.worker import OutboxWorker, default_outbox_lock_owner


def wire_outbox_worker(
    event_outbox_repo: PlatformEventOutboxRepository,
    security: SecurityRegistry,
) -> OutboxWorker | None:
    """OutboxWorker példány, ha az async audit pipeline be van kapcsolva.

    Ha ``security.event_channel`` None (audit_events_async kikapcsolva), None-t ad vissza.
    """
    channel = security.event_channel
    if channel is None:
        return None
    stale = max(1, int(getattr(settings, "platform_event_outbox_stale_lock_sec", 300)))
    return OutboxWorker(
        event_outbox_repo,
        security.dispatcher,
        poll_interval_seconds=channel.poll_interval_seconds,
        max_retries=channel.max_retries,
        retry_delay_seconds=channel.retry_delay_seconds,
        stale_lock_after_sec=stale,
        lock_owner=default_outbox_lock_owner(),
    )
