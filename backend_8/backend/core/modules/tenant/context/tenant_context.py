# backend/core/modules/tenant/context/tenant_context.py
# Feladat: Az aktuális tenant schema ContextVar kezelését tartalmazza. Beállítja, lekéri és reseteli a requesthez tartozó schema nevet, amelyet a DB session search_path kezelése használ. Tenant runtime context helper.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

# Aktuális tenant schema neve (pl. "demo", "acme"). Middleware állítja; session factory ezt használja.
current_tenant_schema: ContextVar[str | None] = ContextVar("current_tenant_schema", default=None)


def run_with_tenant_schema(tenant_slug: str | None, callback: Callable[..., Any], *args, **kwargs) -> Any:
    token = current_tenant_schema.set((tenant_slug or "").strip() or None)
    try:
        return callback(*args, **kwargs)
    finally:
        current_tenant_schema.reset(token)


async def run_async_with_tenant_schema(
    tenant_slug: str | None,
    callback: Callable[..., Awaitable[Any]],
    *args,
    **kwargs,
) -> Any:
    token = current_tenant_schema.set((tenant_slug or "").strip() or None)
    try:
        return await callback(*args, **kwargs)
    finally:
        current_tenant_schema.reset(token)


__all__ = [
    "current_tenant_schema",
    "run_async_with_tenant_schema",
    "run_with_tenant_schema",
]
