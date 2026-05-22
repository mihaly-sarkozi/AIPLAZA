# backend/core/kernel/app/app_lifespan.py
# Feladat: A FastAPI lifespan eseményeit köti össze a kernel runtime konténer életciklusával. Startup alatt inicializálja a perzisztens runtime storage-ot és háttérszolgáltatásokat, majd lefuttatja a manifest startup hookjait; shutdown alatt a manifest hookok után leállítja a runtime-ot és a közös Redis kapcsolatot. Az app factory használja, ezért általános webalkalmazás-életciklus adapter.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.infrastructure.cache.redis_client import close_redis
from core.kernel.app.app_container import AppContainer, get_container
from core.kernel.app.app_manifest import AppManifest

# Felépíti a runtime konténert a manifest alapján
def wire_runtime(manifest: AppManifest) -> AppContainer:
    return get_container(manifest)

# Létrehoz egy asynccontextmanager-t a FastAPI életciklusának kezelésére
def create_lifespan(container: AppContainer, manifest: AppManifest):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        _bootstrap_runtime(container)
        for hook in manifest.startup_hooks:
            result = hook(app)
            if result is not None:
                await result
        try:
            yield
        finally:
            for hook in manifest.shutdown_hooks:
                result = hook(app)
                if result is not None:
                    await result
            _shutdown_runtime(container)

    return lifespan

# Indítja a perzisztens runtime storage és háttérszolgáltatásokat
def _bootstrap_runtime(container: AppContainer) -> None:
    container.initialize_runtime_storage()
    container.start_runtime_services()

# Leállítja a perzisztens runtime storage és háttérszolgáltatásokat
def _shutdown_runtime(container: AppContainer) -> None:
    try:
        container.shutdown()
    finally:
        close_redis()


__all__ = ["create_lifespan", "wire_runtime"]
