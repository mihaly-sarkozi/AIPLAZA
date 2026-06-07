# backend/core/kernel/jobs/enqueue.py
# Feladat: Általános job enqueue a platform outbox táblába (perzisztens, worker által feldolgozott).
# Sárközi Mihály - 2026.06.07

from __future__ import annotations

import logging
from typing import Any

from core.kernel.jobs.errors import JobQueueUnavailableError

logger = logging.getLogger(__name__)


def enqueue_job(
    event_type: str,
    payload: dict[str, Any],
    *,
    idempotency_key: str | None = None,
) -> None:
    """Háttérfeladat ütemezése a platform outbox-on keresztül.

    A payload csak azonosítókat / minimális metaadatot tartalmazzon; a handler tölti a DB-ből.
    ``idempotency_key``: ugyanazzal a kulccsal többszöri hívás nem hoz létre duplikát sort.
    """
    normalized_type = str(event_type or "").strip()
    if not normalized_type:
        raise ValueError("enqueue_job: event_type is required")

    channel = _resolve_job_queue()
    if channel is None or not hasattr(channel, "publish"):
        raise JobQueueUnavailableError(
            "Platform job queue is not configured. Enable platform event outbox worker."
        )

    try:
        channel.publish(normalized_type, payload, idempotency_key=idempotency_key)
    except Exception as exc:
        from core.kernel.events.event_channel import EventDeliveryError

        logger.exception(
            "Platform job enqueue failed",
            extra={"event_type": normalized_type, "idempotency_key": idempotency_key},
        )
        if isinstance(exc, EventDeliveryError):
            raise JobQueueUnavailableError(str(exc)) from exc
        raise JobQueueUnavailableError(
            f"Platform job enqueue failed: {normalized_type}"
        ) from exc


def _resolve_job_queue() -> Any | None:
    from core.kernel.interface.keys import PLATFORM_JOB_QUEUE

    try:
        from core.kernel.deps.registry import get_service

        return get_service(PLATFORM_JOB_QUEUE)
    except RuntimeError:
        pass

    try:
        from core.kernel.app.app_container import get_container

        container = get_container()
        security = getattr(container, "security", None)
        if security is not None:
            return getattr(security, "event_channel", None)
    except Exception:
        return None
    return None


__all__ = ["enqueue_job"]
