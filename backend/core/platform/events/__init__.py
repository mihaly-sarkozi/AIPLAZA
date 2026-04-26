from __future__ import annotations

import importlib

__all__ = [
    "AuditServiceProxy",
    "EmailServiceProxy",
    "EventDeliveryError",
    "SecurityAuditEventChannel",
    "SecurityLoggerProxy",
    "EventDispatcher",
    "EventHandler",
    "register_security_audit_handlers",
    "OutboxWorkItem",
    "PlatformEventOutboxRepository",
    "OutboxWorker",
    "default_outbox_lock_owner",
    "ensure_platform_event_outbox",
]

_LAZY: dict[str, tuple[str, str]] = {
    "AuditServiceProxy": ("core.platform.events.event_channel", "AuditServiceProxy"),
    "EmailServiceProxy": ("core.platform.events.event_channel", "EmailServiceProxy"),
    "EventDeliveryError": ("core.platform.events.event_channel", "EventDeliveryError"),
    "SecurityAuditEventChannel": ("core.platform.events.event_channel", "SecurityAuditEventChannel"),
    "SecurityLoggerProxy": ("core.platform.events.event_channel", "SecurityLoggerProxy"),
    "EventDispatcher": ("core.platform.events.dispatcher", "EventDispatcher"),
    "EventHandler": ("core.platform.events.dispatcher", "EventHandler"),
    "register_security_audit_handlers": ("core.platform.events.handlers", "register_security_audit_handlers"),
    "OutboxWorkItem": ("core.platform.events.outbox", "OutboxWorkItem"),
    "PlatformEventOutboxRepository": ("core.platform.events.outbox", "PlatformEventOutboxRepository"),
    "OutboxWorker": ("core.platform.events.worker", "OutboxWorker"),
    "default_outbox_lock_owner": ("core.platform.events.worker", "default_outbox_lock_owner"),
    "ensure_platform_event_outbox": ("core.platform.events.outbox", "ensure_platform_event_outbox"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
