# Ez a fájl rakja össze a FastAPI alkalmazást a platform- és app-manifestekből.
# Itt történik a middleware-ek, a közös route-ok, az exception handlerek és a manifestből származó hookok bekötése.
# Ez a réteg a belépési pont a deklaratív modulleírás és a ténylegesen futó ASGI alkalmazás között.
# Akkor érdemes ide nyúlni, ha az alkalmazás indulási összeállítása vagy a globális HTTP rétegek viselkedése változik.
from __future__ import annotations

import logging
import os
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.di import get_login_service, get_service, get_tenant_repository, get_token_service
from core.capabilities.auth.router.auth_router import router as auth_api_router
from core.capabilities.users.router.invite_router import router as invite_api_router
from core.capabilities.users.router.user_router import router as user_api_router
from core.extensions.tenant.middleware import TenantMiddleware
from core.extensions.tenant.router.tenant_router import router as tenant_api_router
from core.extensions.tenant.service import register_manifest_tenant_schema_hooks
from core.kernel.config.config_loader import settings
from core.kernel.logging.observability import configure_structured_logging, increment_metric, log_exception_event, log_structured_event
from core.kernel.middleware.observability import CorrelationIdMiddleware, RequestTimingMiddleware
from core.kernel.middleware.security import AuthMiddleware, CSRFMiddleware, SecurityHeadersMiddleware
from core.kernel.security.security_bootstrap import assert_security_ready
from core.platform.manifest import AppManifest, PlatformManifest, RouteRegistration, merge_app_manifest
from core.platform.service_keys import (
    PLATFORM_DOMAIN_ROUTING_POLICY,
    PLATFORM_TENANT_LIFECYCLE_POLICY,
)
from core.kernel.security.rate_limit import limiter
from lang.messages import get_message, lang_from_request

configure_structured_logging()


# Ez a függvény felépíti a(z) cors origin regex logikáját.
def _build_cors_origin_regex() -> str:
    base = re.escape(settings.tenant_base_domain)
    if settings.tenant_base_domain == "local":
        return rf"^https?://(localhost|([a-z0-9][a-z0-9-]*\.)?{base})(:\d+)?$"
    return rf"^https?://([a-z0-9][a-z0-9-]*\.)?{base}(:\d+)?$"


# Ez a függvény regisztrálja a(z) exception handlers logikáját.
def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RateLimitExceeded)
    def rate_limit_handler(request, exc):
        increment_metric("platform.rate_limit.hit.count", 1.0)
        log_structured_event(
            "core.http",
            "request.rate_limited",
            level=logging.WARNING,
            path=str(getattr(request, "url", "")),
            method=getattr(request, "method", None),
            tenant_slug=getattr(getattr(request, "state", object()), "tenant_slug", None),
            tenant_id=getattr(getattr(request, "state", object()), "tenant_id", None),
            user_id=getattr(getattr(getattr(request, "state", object()), "user", None), "id", None),
        )
        return JSONResponse(
            status_code=429,
            content={"detail": "Túl sok kérés. Próbáld újra később."},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if exc.status_code >= 500:
            log_exception_event(
                "core.http",
                "request.http_exception",
                exc,
                path=str(request.url.path),
                method=request.method,
                status_code=exc.status_code,
                tenant_slug=getattr(request.state, "tenant_slug", None),
                tenant_id=getattr(request.state, "tenant_id", None),
                user_id=getattr(getattr(request.state, "user", None), "id", None),
            )
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            lang = lang_from_request(request)
            content = dict(exc.detail)
            content["message"] = get_message(content["code"], lang)
            return JSONResponse(status_code=exc.status_code, content={"detail": content})
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code >= 500:
            log_exception_event(
                "core.http",
                "request.starlette_http_exception",
                exc,
                path=str(request.url.path),
                method=request.method,
                status_code=exc.status_code,
                tenant_slug=getattr(request.state, "tenant_slug", None),
                tenant_id=getattr(request.state, "tenant_id", None),
                user_id=getattr(getattr(request.state, "user", None), "id", None),
            )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        increment_metric("platform.request.unhandled_error.count", 1.0)
        log_exception_event(
            "core.http",
            "request.unhandled_exception",
            exc,
            path=str(request.url.path),
            method=request.method,
            status_code=500,
            tenant_slug=getattr(request.state, "tenant_slug", None),
            tenant_id=getattr(request.state, "tenant_id", None),
            user_id=getattr(getattr(request.state, "user", None), "id", None),
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Ez a függvény regisztrálja a(z) middlewares logikáját.
def _register_middlewares(app: FastAPI, manifest: PlatformManifest) -> None:
    if os.environ.get("DISABLE_CSRF") != "1":
        app.add_middleware(CSRFMiddleware)

    light_paths = manifest.light_paths or tuple(
        p.strip()
        for p in (getattr(settings, "auth_light_paths", "") or "").split(",")
        if p.strip()
    )

    app.add_middleware(
        AuthMiddleware,
        token_service=get_token_service(),
        login_service=get_login_service(),
        light_paths=light_paths,
    )
    app.add_middleware(
        TenantMiddleware,
        tenant_repo=get_tenant_repository(),
        base_domain=settings.tenant_base_domain,
        multi_tenant_enabled=settings.multi_tenant_enabled,
        install_host=settings.install_host,
        single_tenant_slug=settings.single_tenant_slug,
        routing_policy=get_service(PLATFORM_DOMAIN_ROUTING_POLICY),
        lifecycle_policy=get_service(PLATFORM_TENANT_LIFECYCLE_POLICY),
    )

    trusted_hosts = [h.strip() for h in (getattr(settings, "trusted_hosts", "") or "").split(",") if h.strip()]
    if trusted_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

    app.add_middleware(RequestTimingMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_origin_regex=_build_cors_origin_regex(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID", "X-Correlation-ID"],
        expose_headers=["X-Request-ID", "X-Correlation-ID", "X-Response-Time-Ms", "X-Timing-Spans"],
    )


# Ez a függvény regisztrálja a(z) routes logikáját.
def _register_routes(app: FastAPI, manifest: PlatformManifest) -> None:
    core_routes = (
        RouteRegistration(router=auth_api_router, prefix="/api", tags=("auth",)),
        RouteRegistration(router=tenant_api_router, prefix="/api", tags=("tenant",)),
        RouteRegistration(router=user_api_router, prefix="/api", tags=("users",)),
        RouteRegistration(router=invite_api_router, prefix="/api", tags=("users-invite",)),
    )
    for route in core_routes:
        app.include_router(route.router, prefix=route.prefix, tags=list(route.tags))
    for route in manifest.routers:
        app.include_router(route.router, prefix=route.prefix, tags=list(route.tags))


# Ez a függvény regisztrálja a(z) manifest hookok logikáját.
def _register_manifest_hooks(manifest: PlatformManifest) -> None:
    for bootstrap in manifest.bootstrap_hooks:
        bootstrap()
    register_manifest_tenant_schema_hooks(manifest)


# Ez a függvény létrehozza a(z) platform alkalmazás logikáját.
def create_platform_app(manifest: PlatformManifest) -> FastAPI:
    assert_security_ready(settings)
    _register_manifest_hooks(manifest)

    # Ez az aszinkron függvény a(z) lifespan logikáját valósítja meg.
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        for hook in manifest.startup_hooks:
            result = hook(app)
            if result is not None:
                await result
        yield
        for hook in manifest.shutdown_hooks:
            result = hook(app)
            if result is not None:
                await result

    app = FastAPI(
        title=manifest.app_name,
        description=manifest.description,
        version=manifest.version,
        docs_url=manifest.docs_url,
        redoc_url=manifest.redoc_url,
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.state.platform_manifest = manifest
    _register_exception_handlers(app)
    _register_middlewares(app, manifest)
    _register_routes(app, manifest)
    return app


# Ez a függvény létrehozza a(z) alkalmazás from manifests logikáját.
def create_app_from_manifests(platform_manifest: PlatformManifest, app_manifest: AppManifest) -> FastAPI:
    return create_platform_app(merge_app_manifest(platform_manifest, app_manifest))
