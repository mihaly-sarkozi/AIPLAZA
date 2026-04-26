"""Standalone outbox worker belépő pont.

Használat:
    INSTANCE_ROLE=worker python -m core.platform.events

    Vagy Docker-containerben:
        CMD ["python", "-m", "core.platform.events"]

A worker:
  1. Betölti a konfigurációt (.env / env var)
  2. Csatlakozik az adatbázishoz
  3. Felépíti az EventDispatcher-t (biztonsági audit handler-ekkel)
  4. Elindítja az OutboxWorker-t blokkoló módban
  5. SIGTERM / SIGINT hatására tisztán leáll

Szükséges env var-ok (amelyek a web-processhez is kellenek):
  DATABASE_URL, JWT_SECRET, SMTP_* (vagy .env fájl)

Worker-specifikus:
  INSTANCE_ROLE=worker
"""
from __future__ import annotations

import logging
import os
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)

_log = logging.getLogger("core.events.worker.__main__")


def _build_and_run() -> None:
    from core.kernel.config.environment import load_project_env
    from core.kernel.config.instance_role import InstanceRole, get_instance_role
    from core.platform.bootstrap.infrastructure import build_infrastructure
    from core.platform.bootstrap.security import build_security
    from core.capabilities.audit.service.audit_service import AuditService
    from core.platform.events.dispatcher import EventDispatcher
    from core.platform.events.handlers import register_security_audit_handlers
    from core.platform.events.outbox import PlatformEventOutboxRepository, ensure_platform_event_outbox
    from core.platform.events.worker import OutboxWorker
    from core.kernel.config.config_loader import settings

    load_project_env()

    role = get_instance_role()
    if role == InstanceRole.WEB:
        _log.error(
            "INSTANCE_ROLE=web – ebben a mód a worker nem futtatható. "
            "Állítsd be INSTANCE_ROLE=worker vagy INSTANCE_ROLE=combined értékre."
        )
        sys.exit(1)

    _log.info("Outbox worker indul (INSTANCE_ROLE=%s)…", role.value)

    infra = build_infrastructure()
    db_sf = infra.db_session_factory

    audit_service = AuditService(infra.repositories.audit_repo)
    outbox_repo = PlatformEventOutboxRepository(db_sf)

    ensure_platform_event_outbox(db_sf.engine)

    security = build_security(
        audit_service=audit_service,
        email_service=infra.email_service,
        outbox_repository=outbox_repo,
    )

    dispatcher = EventDispatcher()
    register_security_audit_handlers(
        dispatcher,
        security_logger=security.base_security_logger,
        audit_service=audit_service,
        email_service=infra.email_service,
    )

    poll_interval = max(
        0.1, float(getattr(settings, "platform_event_outbox_poll_interval_sec", 1.0))
    )
    max_retries = max(1, int(getattr(settings, "platform_event_outbox_max_retries", 10)))
    retry_delay = max(1, int(getattr(settings, "platform_event_outbox_retry_delay_sec", 5)))

    stale_lock = max(1, int(getattr(settings, "platform_event_outbox_stale_lock_sec", 300)))

    worker = OutboxWorker(
        outbox_repo,
        dispatcher,
        poll_interval_seconds=poll_interval,
        max_retries=max_retries,
        retry_delay_seconds=retry_delay,
        stale_lock_after_sec=stale_lock,
        lock_owner=default_outbox_lock_owner(),
    )

    # SIGTERM / SIGINT tiszta leállást eredményez
    def _handle_signal(sig, frame):
        _log.info("Stop signal (%s) érkezett – a worker leáll…", sig)
        worker.stop(timeout=10.0)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    _log.info("Outbox worker fut. Ctrl+C vagy SIGTERM hatására leáll.")
    worker.run_blocking()


if __name__ == "__main__":
    _build_and_run()
