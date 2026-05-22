# backend/core/kernel/audit/__init__.py
# Feladat: Stabil public audit exportfelulet app modulok szamara. Elrejti az audit
# infrastruktura belso namespace-eit, hogy az apps reteg ne importaljon kozvetlenul
# core.infrastructure.* modulokat.

from __future__ import annotations

from dataclasses import dataclass, field
import importlib
from typing import Any, Protocol, runtime_checkable

from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction


AuditAction = AuditLogAction


@dataclass(frozen=True)
class AuditEvent:
    action: AuditAction
    user_id: int | None = None
    actor_type: str | None = None
    event_name: str | None = None
    outcome: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    correlation_id: str | None = None
    details: dict[str, Any] | None = field(default=None)
    ip: str | None = None
    user_agent: str | None = None


@runtime_checkable
class AuditPort(Protocol):
    def log(
        self,
        action: AuditAction,
        *,
        user_id: int | None = None,
        actor_type: str | None = None,
        event_name: str | None = None,
        outcome: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        correlation_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None: ...


AuditInterface = AuditPort


class AuditEventFactory:
    def build(
        self,
        action: AuditAction,
        *,
        user_id: int | None = None,
        actor_type: str | None = None,
        event_name: str | None = None,
        outcome: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        correlation_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEvent:
        return AuditEvent(
            action=AuditAction(str(action)),
            user_id=user_id,
            actor_type=actor_type,
            event_name=event_name,
            outcome=outcome,
            target_type=target_type,
            target_id=target_id,
            correlation_id=correlation_id,
            details=dict(details or {}) if details is not None else None,
            ip=ip,
            user_agent=user_agent,
        )

    def emit(self, audit: AuditPort, event: AuditEvent) -> None:
        audit.log(
            event.action,
            user_id=event.user_id,
            actor_type=event.actor_type,
            event_name=event.event_name,
            outcome=event.outcome,
            target_type=event.target_type,
            target_id=event.target_id,
            correlation_id=event.correlation_id,
            details=event.details,
            ip=event.ip,
            user_agent=event.user_agent,
        )


__all__ = [
    "AuditAction",
    "AuditEvent",
    "AuditEventFactory",
    "AuditInterface",
    "AuditLogAction",
    "AuditPort",
    "AuditService",
]


def __getattr__(name: str):
    if name == "AuditService":
        return getattr(importlib.import_module("core.infrastructure.audit.service.audit_service"), "AuditService")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
