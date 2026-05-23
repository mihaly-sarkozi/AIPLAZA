# backend/core/kernel/interface/observability.py
# Feladat: Appok számára stabil observability és audit interfészeket ad. Könnyű dataclass és Protocol típusokat definiál, valamint vékony wrapper függvényeket biztosít metrikához, strukturált loghoz és observability scope-hoz. Public core interface, hogy app modulok ne a logging implementáció belsejét importálják.
# Sárközi Mihály - 2026.05.21

"""Pure platform observability interfaces."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable


@dataclass(frozen=True)
class ObservabilityContext:
    correlation_id: str | None = None
    request_id: str | None = None
    tenant_id: int | None = None
    tenant_slug: str | None = None
    user_id: int | None = None
    event_name: str | None = None
    instance_role: str | None = None
    worker_role: str | None = None
    worker_run_id: str | None = None
    batch_id: str | None = None


@dataclass(frozen=True)
class AuditTarget:
    resource_type: str | None = None
    resource_id: str | None = None


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    occurred_at: str
    actor_user_id: int | None = None
    actor_type: str = "system"
    tenant_id: int | None = None
    tenant_slug: str | None = None
    correlation_id: str | None = None
    outcome: str | None = None
    target: AuditTarget = field(default_factory=AuditTarget)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class MetricsSink(Protocol):
    def increment(self, name: str, value: float = 1.0, *, unit: str = "count", tags: Mapping[str, Any] | None = None) -> None: ...

    def observe(self, name: str, value: float, *, unit: str = "count", tags: Mapping[str, Any] | None = None) -> None: ...


@runtime_checkable
class AuditSink(Protocol):
    def log_event(self, event: AuditEvent) -> None: ...


def log_structured_event(
    logger_name: str,
    event: str,
    *,
    level: int,
    **fields: Any,
) -> None:
    from core.kernel.logging.observability import log_structured_event as _log_structured_event

    _log_structured_event(logger_name, event, level=level, **fields)


def increment_metric(name: str, value: float = 1.0, *, unit: str = "count", tags: Mapping[str, Any] | None = None) -> None:
    from core.kernel.logging.observability import increment_metric as _increment_metric

    _increment_metric(name, value, unit=unit, tags=dict(tags or {}))


def observe_metric(name: str, value: float, *, unit: str = "count", tags: Mapping[str, Any] | None = None) -> None:
    from core.kernel.logging.observability import observe_metric as _observe_metric

    _observe_metric(name, value, unit=unit, tags=dict(tags or {}))


@contextmanager
def observability_scope(**fields: Any):
    from core.kernel.logging.observability import observability_scope as _observability_scope

    with _observability_scope(**fields):
        yield


__all__ = [
    "AuditEvent",
    "AuditSink",
    "AuditTarget",
    "MetricsSink",
    "ObservabilityContext",
    "increment_metric",
    "log_structured_event",
    "observe_metric",
    "observability_scope",
]
