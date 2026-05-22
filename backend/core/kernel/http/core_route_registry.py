# backend/core/kernel/http/core_route_registry.py
# Feladat: A core HTTP route-ok és a manifestből érkező app route-ok FastAPI apphoz kötését végzi. Explicit listázza a kernelhez tartozó auth, tenant és user routereket, majd hozzáadja a modulok manifest routereit. Core HTTP assembly elem, amelyet az app_factory hív az alkalmazás építésekor.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from fastapi import FastAPI

from core.kernel.app.app_manifest import AppManifest
from core.kernel.interface.routing import RouteRegistration
from core.modules.auth.router.auth_router import router as auth_api_router
from core.modules.tenant.router.tenant_router import router as tenant_api_router
from core.modules.users.router.invite_router import router as invite_api_router
from core.modules.users.router.user_router import router as user_api_router


def core_http_routes() -> tuple[RouteRegistration, ...]:
    return (
        RouteRegistration(router=auth_api_router, prefix="/api", tags=("auth",)),
        RouteRegistration(router=tenant_api_router, prefix="/api", tags=("tenant",)),
        RouteRegistration(router=user_api_router, prefix="/api", tags=("users",)),
        RouteRegistration(router=invite_api_router, prefix="/api", tags=("users-invite",)),
    )


def register_routes(app: FastAPI, manifest: AppManifest) -> None:
    for route in core_http_routes():
        app.include_router(route.router, prefix=route.prefix, tags=list(route.tags))
    for route in manifest.routers:
        app.include_router(route.router, prefix=route.prefix, tags=list(route.tags))


__all__ = ["core_http_routes", "register_routes"]
