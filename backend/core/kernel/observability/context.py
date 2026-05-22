# backend/core/kernel/observability/context.py
# Feladat: Request, tenant, user, worker és correlation adatokat tárol ContextVar alapon. Middleware-ek, worker loopok és service-ek bindelik ezt a kontextust, a log és event emitterek pedig innen olvassák ki az alap mezőket. Core observability állapotkezelő, amely async/request környezetben is izolált marad.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Any

_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "observability_context",
    default={},
)


def get_observability_context() -> dict[str, Any]:
    return dict(_context.get())


def bind_observability_context(**fields: Any):
    current = get_observability_context()
    for key, value in fields.items():
        if value is None:
            current.pop(key, None)
        else:
            current[key] = value
    return _context.set(current)


def reset_observability_context(token) -> None:
    _context.reset(token)


@contextmanager
def observability_scope(**fields: Any):
    token = bind_observability_context(**fields)
    try:
        yield
    finally:
        reset_observability_context(token)


def set_correlation_id(value: str | None) -> None:
    bind_observability_context(correlation_id=(value or "").strip() or None)


def set_request_id(value: str | None) -> None:
    bind_observability_context(request_id=(value or "").strip() or None)


def set_tenant_context(*, tenant_id: int | None = None, tenant_slug: str | None = None) -> None:
    bind_observability_context(tenant_id=tenant_id, tenant_slug=tenant_slug)


def set_user_id(value: int | None) -> None:
    bind_observability_context(user_id=value)


def get_correlation_id() -> str | None:
    value = get_observability_context().get("correlation_id")
    return str(value) if value else None


def get_request_id() -> str | None:
    value = get_observability_context().get("request_id")
    return str(value) if value else None


def clear_correlation_id() -> None:
    bind_observability_context(correlation_id=None, request_id=None)


def clear_observability_context() -> None:
    _context.set({})


__all__ = [
    "bind_observability_context",
    "clear_correlation_id",
    "clear_observability_context",
    "get_correlation_id",
    "get_observability_context",
    "get_request_id",
    "observability_scope",
    "reset_observability_context",
    "set_correlation_id",
    "set_request_id",
    "set_tenant_context",
    "set_user_id",
]
