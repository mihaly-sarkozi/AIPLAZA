# backend/core/kernel/app/app_factory.py
# Feladat: FastAPI alkalmazást állít össze egy kész AppManifest és settings objektum alapján. Elindítja a biztonsági startup ellenőrzéseket, beköti a runtime konténert, middleware-eket, route-okat, exception handlereket, telemetriát és lifespan kezelést. A `backend/main.py` tölti be, ezért ez az alkalmazásindítás legfontosabb általános kernel belépési pontja.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from fastapi import FastAPI

from core.kernel.app.app_bootstrap import bootstrap_manifest_runtime
from core.kernel.app.app_manifest import AppManifest

from core.kernel.http.exception_handlers import register_exception_handlers
from core.kernel.http.middleware_registration import register_middlewares
from core.kernel.http.core_route_registry import register_routes
from core.kernel.logging.logging_config import configure_structured_logging
from core.kernel.logging.telemetry import configure_runtime_telemetry
from core.kernel.app.app_lifespan import create_lifespan, wire_runtime
from core.kernel.security.rate_limit import limiter
from core.kernel.security.security_startup_checks import run_security_startup_checks


def create_app_from_manifest(
    manifest: AppManifest,
    *,
    settings: object,
) -> FastAPI:
    
    # Log szint beállítása a konfigurációból
    configure_structured_logging(level_name=getattr(settings, "log_level", "INFO"))
    
    # Ha a startup check elbukik, a rendszer nem indul el.
    run_security_startup_checks(settings)

    # A runtime manifest alapján felépített konténer kötése a FastAPI app-hoz
    container = wire_runtime(manifest)
    
    # A manifest bootstrap és tenant schema hookok futtatása
    bootstrap_manifest_runtime(manifest)

    # A FastAPI app létrehozása a manifest alapján
    docs_url, redoc_url, openapi_url = _openapi_urls_from_settings(settings)
    app = FastAPI(
        title=manifest.app_name,
        description=manifest.description,
        version=manifest.version,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=create_lifespan(container, manifest),
    )
    
    # A runtime telemetria konfigurálása
    configure_runtime_telemetry(settings, app)
    
    # A rate limit konfigurálása
    app.state.limiter = limiter
    app.state.container = container
    
    # A manifest state-be kerül
    app.state.manifest = manifest

    # A kivétel kezelők regisztrálása
    register_exception_handlers(app)
    
    # A middlewarek regisztrálása
    register_middlewares(app, manifest)
    
    # A routek regisztrálása
    register_routes(app, manifest)
    
    # A FastAPI app visszaadása
    return app

def _openapi_urls_from_settings(settings: object) -> tuple[str | None, str | None, str | None]:
    if not bool(getattr(settings, "openapi_enabled", True)):
        return None, None, None
    return (
        getattr(settings, "docs_url", "/docs"),
        getattr(settings, "redoc_url", "/redoc"),
        getattr(settings, "openapi_url", "/openapi.json"),
    )


__all__ = ["create_app_from_manifest"]
