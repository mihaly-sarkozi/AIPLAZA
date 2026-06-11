# backend/core/kernel/events/worker_entrypoint.py
# Feladat: A standalone worker process assembly-je: logging, instance role ellenőrzés, infrastruktúra, security szolgáltatások, dispatcher és worker példányok összekötése. A __main__.py csak ide delegál, így a futtatási belépőpont kicsi marad, de a process indítás tesztelhető és átlátható. Core runtime adapter worker konténerekhez és dedikált háttérfolyamatokhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib
import logging
import signal
import sys
import threading

_log = logging.getLogger("core.events.worker.__main__")


def build_and_run_worker_process() -> None:
    from core.kernel.runtime.instance_role import (
        InstanceRole,
        get_instance_role,
        should_run_standalone_billing_worker,
        should_run_standalone_outbox_worker,
    )
    from core.kernel.bootstrap.infrastructure import build_infrastructure
    from core.kernel.bootstrap.security import build_security
    from core.infrastructure.audit.service.audit_service import AuditService
    from core.kernel.events.dispatcher import EventDispatcher
    from core.kernel.events.handlers import register_security_audit_handlers
    from core.kernel.events.outbox import PlatformEventOutboxRepository, ensure_platform_event_outbox
    from core.kernel.events.worker import OutboxWorker, default_outbox_lock_owner
    from core.kernel.config.config_loader import settings
    from core.kernel.logging.logging_config import configure_structured_logging

    configure_structured_logging(level_name=getattr(settings, "log_level", "INFO"))

    role = get_instance_role()
    if role == InstanceRole.WEB:
        _log.error(
            "INSTANCE_ROLE=web – ebben a mód a worker nem futtatható. "
            "Állítsd be INSTANCE_ROLE=worker vagy INSTANCE_ROLE=combined értékre."
        )
        sys.exit(1)

    _log.info("Worker process indul (INSTANCE_ROLE=%s)…", role.value)

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
    dispatcher = _build_dispatcher(
        security_logger=security.base_security_logger,
        audit_service=audit_service,
        email_service=infra.email_service,
        db_session_factory=db_sf,
    )
    outbox_worker = _build_outbox_worker(
        outbox_repo=outbox_repo,
        dispatcher=dispatcher,
        settings=settings,
    )
    billing_worker, billing_started = _start_billing_worker_if_enabled(
        db_sf=db_sf,
        infra=infra,
        should_run=should_run_standalone_billing_worker(),
    )
    _install_signal_handlers(
        outbox_worker=outbox_worker,
        billing_worker=billing_worker,
        billing_started=billing_started,
    )

    if not should_run_standalone_outbox_worker():
        _log.warning("Standalone outbox worker loop letiltva (OUTBOX_WORKER_LOOP_ENABLED=0).")
        if billing_started:
            _log.info("Csak billing worker fut. Ctrl+C vagy SIGTERM hatására leáll.")
            stop = threading.Event()
            while not stop.wait(3600):
                pass
        return
    _log.info("Outbox worker fut. Ctrl+C vagy SIGTERM hatására leáll.")
    outbox_worker.run_blocking()


def _build_dispatcher(*, security_logger, audit_service, email_service, db_session_factory=None):
    from core.kernel.events.dispatcher import EventDispatcher
    from core.kernel.events.handlers import register_security_audit_handlers

    dispatcher = EventDispatcher()
    register_security_audit_handlers(
        dispatcher,
        security_logger=security_logger,
        audit_service=audit_service,
        email_service=email_service,
    )
    try:
        kb_events_module = importlib.import_module("apps.kb.events")
        register_kb_event_handlers = getattr(kb_events_module, "register_kb_event_handlers", None)
        if callable(register_kb_event_handlers):
            register_kb_event_handlers(dispatcher, session_factory=db_session_factory)
    except Exception as exc:
        _log.warning("KB outbox handler regisztráció kihagyva: %s", exc)
    return dispatcher


def _build_outbox_worker(*, outbox_repo, dispatcher, settings):
    from core.kernel.events.worker import OutboxWorker, default_outbox_lock_owner

    poll_interval = max(
        0.1, float(getattr(settings, "platform_event_outbox_poll_interval_sec", 1.0))
    )
    max_retries = max(1, int(getattr(settings, "platform_event_outbox_max_retries", 10)))
    retry_delay = max(1, int(getattr(settings, "platform_event_outbox_retry_delay_sec", 5)))
    stale_lock = max(1, int(getattr(settings, "platform_event_outbox_stale_lock_sec", 300)))
    lease = max(1, int(getattr(settings, "platform_event_outbox_lease_sec", 300)))
    handler_timeout = max(1, int(getattr(settings, "platform_event_handler_timeout_sec", 15)))
    return OutboxWorker(
        outbox_repo,
        dispatcher,
        poll_interval_seconds=poll_interval,
        max_retries=max_retries,
        retry_delay_seconds=retry_delay,
        stale_lock_after_sec=stale_lock,
        handler_timeout_seconds=handler_timeout,
        lease_seconds=lease,
        lock_owner=default_outbox_lock_owner(),
    )


def _start_billing_worker_if_enabled(*, db_sf, infra, should_run: bool) -> tuple[object | None, bool]:
    if not should_run:
        _log.info("Standalone billing worker loop letiltva (BILLING_WORKER_LOOP_ENABLED=0).")
        return None, False

    billing_repositories = importlib.import_module("apps.billing.repositories")
    billing_service_module = importlib.import_module("apps.billing.service")
    billing_worker_module = importlib.import_module("apps.billing.worker")
    BillingRepository = getattr(billing_repositories, "BillingRepository")
    BillingService = getattr(billing_service_module, "BillingService")
    BillingWorker = getattr(billing_worker_module, "BillingWorker")
    billing_service = BillingService(
        repo=BillingRepository(db_sf),
        tenant_repo=infra.repositories.tenant_repo,
        session_factory=db_sf,
        user_repository=infra.repositories.user_repo,
        email_service=infra.email_service,
    )
    billing_service.ensure_storage()
    billing_worker = BillingWorker()
    billing_worker.start()
    _log.info("Standalone billing worker loop elindult.")
    return billing_worker, True


def _install_signal_handlers(*, outbox_worker, billing_worker, billing_started: bool) -> None:
    def _handle_signal(sig, frame):
        _log.info("Stop signal (%s) érkezett – a worker leáll…", sig)
        if billing_worker is not None and billing_started:
            billing_worker.stop()
        outbox_worker.stop(timeout=10.0)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)


__all__ = ["build_and_run_worker_process"]
