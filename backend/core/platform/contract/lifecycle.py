"""Lifecycle hook interfaces for platform modules."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

#: ASGI lifespan startup / shutdown hook (manifest + AppModule.startup_hooks / shutdown_hooks)
LifecycleHook = Callable[[Any], Awaitable[None] | None]

#: Szinkron hook tenant séma bővítéshez (provisioning / migráció)
TenantSchemaRegistrar = Callable[[], None]

#: Szinkron hook a FastAPI app létrejötte előtt (manifest.bootstrap_hooks, AppManifest.bootstrap_hooks)
BootstrapHook = Callable[[], None]

__all__ = ["BootstrapHook", "LifecycleHook", "TenantSchemaRegistrar"]

