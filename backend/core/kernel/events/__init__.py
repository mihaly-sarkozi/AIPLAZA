# backend/core/kernel/events/__init__.py
# Feladat: Az events csomag publikus, lazy importos exportfelületét adja. A gyakran használt dispatcher, event channel, outbox repository és worker típusokat úgy teszi elérhetővé, hogy a csomag importja ne húzza be azonnal az összes runtime függőséget. Core framework API, amelyet bootstrap, runtime wiring és tesztek is használhatnak.
# Sárközi Mihály - 2026.05.21

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
    "HandlerRegistry",
    "IdempotencyService",
    "register_security_audit_handlers",
    "OutboxHealthService",
    "OutboxWorkItem",
    "PlatformEventOutboxRepository",
    "OutboxWorker",
    "default_outbox_lock_owner",
    "ensure_platform_event_outbox",
]

_LAZY: dict[str, tuple[str, str]] = {
    "AuditServiceProxy": ("core.kernel.events.event_channel", "AuditServiceProxy"),
    "EmailServiceProxy": ("core.kernel.events.event_channel", "EmailServiceProxy"),
    "EventDeliveryError": ("core.kernel.events.event_channel", "EventDeliveryError"),
    "SecurityAuditEventChannel": ("core.kernel.events.event_channel", "SecurityAuditEventChannel"),
    "SecurityLoggerProxy": ("core.kernel.events.event_channel", "SecurityLoggerProxy"),
    "EventDispatcher": ("core.kernel.events.dispatcher", "EventDispatcher"),
    "EventHandler": ("core.kernel.events.dispatcher", "EventHandler"),
    "HandlerRegistry": ("core.kernel.events.dispatcher", "HandlerRegistry"),
    "IdempotencyService": ("core.kernel.events.outbox", "IdempotencyService"),
    "register_security_audit_handlers": ("core.kernel.events.handlers", "register_security_audit_handlers"),
    "OutboxHealthService": ("core.kernel.events.outbox", "OutboxHealthService"),
    "OutboxWorkItem": ("core.kernel.events.outbox", "OutboxWorkItem"),
    "PlatformEventOutboxRepository": ("core.kernel.events.outbox", "PlatformEventOutboxRepository"),
    "OutboxWorker": ("core.kernel.events.worker", "OutboxWorker"),
    "default_outbox_lock_owner": ("core.kernel.events.worker", "default_outbox_lock_owner"),
    "ensure_platform_event_outbox": ("core.kernel.events.outbox", "ensure_platform_event_outbox"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
