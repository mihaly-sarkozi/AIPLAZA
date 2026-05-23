# backend/core/kernel/events/handlers.py
# Feladat: A beépített security, audit és email outbox események handler factory-jeit adja. A dispatcherbe regisztrálható függvényeket készít, amelyek idempotensen visszahívják a valódi logger/service objektumokat. Core default handler készlet, amelyet web bootstrap és standalone worker entrypoint is betölt.
# Sárközi Mihály - 2026.05.21

"""Beépített biztonsági audit eseménykezelők.

Ez a modul tartalmazza a konkrét handler-factory függvényeket, amelyek
korábban a SecurityAuditEventChannel._worker_loop()-ban hardcode-olva éltek.

A handler-ek kiemelésének előnyei:
  - Tesztelhetők dependency injection-nel (mock logger, mock service)
  - Futhatnak web-processben, dedikált worker-szálban vagy külön worker-processben
  - Idempotensnek kell lenniük: ugyanaz az outbox sor retry esetén újra futhat
  - Új event típushoz nincs szükség az event_channel módosítására

Regisztrálás az EventDispatcher-be a core/kernel/bootstrap/security.py-ban
történik a register_security_audit_handlers() hívásával.
"""
from __future__ import annotations

import logging
from typing import Any

from core.kernel.logging.observability import observability_scope

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Handler factory-k
# ---------------------------------------------------------------------------


def make_security_handler(security_logger: Any):
    """Security logger proxy meghívó: method+args+kwargs → security_logger.method(...)."""
    def handle_security(payload: dict[str, Any]) -> None:
        meta = payload.get("_meta") or {}
        method = payload.get("method")
        args = tuple(payload.get("args", ()))
        kwargs = payload.get("kwargs", {})
        with observability_scope(
            correlation_id=meta.get("correlation_id"),
            request_id=meta.get("request_id"),
            tenant_id=meta.get("tenant_id"),
            tenant_slug=meta.get("tenant_slug"),
            user_id=meta.get("user_id"),
            event_name=meta.get("event_name"),
        ):
            if method and hasattr(security_logger, method):
                getattr(security_logger, method)(*args, **kwargs)
            else:
                _log.warning("security handler: ismeretlen metódus: %r", method)

    return handle_security


def make_audit_handler(audit_service: Any):
    """Audit log bejegyzés írása az audit_service-en keresztül tenant kontextussal."""
    from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
    from core.modules.tenant.context.tenant_context import current_tenant_schema

    def handle_audit(payload: dict[str, Any]) -> None:
        meta = payload.get("_meta") or {}
        tenant_slug = payload.get("tenant_slug") or meta.get("tenant_slug")
        token = current_tenant_schema.set(tenant_slug)
        try:
            with observability_scope(
                correlation_id=meta.get("correlation_id"),
                request_id=meta.get("request_id"),
                tenant_id=meta.get("tenant_id"),
                tenant_slug=tenant_slug,
                user_id=payload.get("user_id") or meta.get("user_id"),
                event_name=meta.get("event_name"),
            ):
                audit_service.log(
                    AuditLogAction(str(payload["action"])),
                    user_id=payload.get("user_id"),
                    actor_type=payload.get("actor_type"),
                    event_name=payload.get("event_name"),
                    outcome=payload.get("outcome"),
                    target_type=payload.get("target_type"),
                    target_id=payload.get("target_id"),
                    details=payload.get("details"),
                    ip=payload.get("ip"),
                    user_agent=payload.get("user_agent"),
                    correlation_id=payload.get("correlation_id") or meta.get("correlation_id"),
                )
        finally:
            current_tenant_schema.reset(token)

    return handle_audit


def make_email_2fa_handler(email_service: Any):
    """2FA email küldés."""
    def handle_email_2fa(payload: dict[str, Any]) -> None:
        ok = email_service.send_2fa_code(
            payload.get("to_email", ""),
            payload.get("code", ""),
            pending_token=payload.get("pending_token"),
            lang=payload.get("lang"),
            expiry_minutes=int(payload.get("expiry_minutes", 10) or 10),
        )
        if not ok:
            raise RuntimeError("2FA email küldés sikertelen")

    return handle_email_2fa


def make_email_invite_handler(email_service: Any):
    """Meghívó / jelszóbeállító email küldés."""
    def handle_email_invite(payload: dict[str, Any]) -> None:
        ok = email_service.send_set_password_invite(
            payload.get("to_email", ""),
            payload.get("set_password_link", ""),
            lang=payload.get("lang"),
        )
        if not ok:
            raise RuntimeError("Meghívó email küldés sikertelen")

    return handle_email_invite


# ---------------------------------------------------------------------------
# Összesített regisztrációs belépési pont
# ---------------------------------------------------------------------------


def register_security_audit_handlers(
    dispatcher,
    *,
    security_logger: Any,
    audit_service: Any,
    email_service: Any,
) -> None:
    """Regisztrálja az összes beépített biztonsági audit handler-t az EventDispatcher-be.

    Startup-kor egyszer hívandó, még mielőtt bármelyik event publikálódna.
    """
    dispatcher.register("security", make_security_handler(security_logger))
    dispatcher.register("audit", make_audit_handler(audit_service))
    dispatcher.register("email_2fa", make_email_2fa_handler(email_service))
    dispatcher.register("email_invite", make_email_invite_handler(email_service))


__all__ = [
    "make_audit_handler",
    "make_email_2fa_handler",
    "make_email_invite_handler",
    "make_security_handler",
    "register_security_audit_handlers",
]
