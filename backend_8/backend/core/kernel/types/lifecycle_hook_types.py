# backend/core/kernel/types/lifecycle_hook_types.py
# Feladat: Lifecycle, bootstrap és tenant schema hook függvénytípusok közös aliasai. Ezeket a BaseAppModule és AppManifest használja annak leírására, milyen callable-k futnak induláskor, leállításkor vagy tenant séma bővítéskor. Core type-only contract, amely nem importál runtime implementációt.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Any, Awaitable, Callable

# ASGI lifespan startup / shutdown hook (AppManifest + BaseAppModule startup/shutdown hookok)
LifecycleHook = Callable[[Any], Awaitable[None] | None]

# Szinkron hook tenant séma bővítéshez (provisioning / migráció)
TenantSchemaRegistrar = Callable[[], None]

# Szinkron hook a FastAPI app létrejötte előtt (AppManifest bootstrap hookok)
BootstrapHook = Callable[[], None]

__all__ = ["BootstrapHook", "LifecycleHook", "TenantSchemaRegistrar"]
