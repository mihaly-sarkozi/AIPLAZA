# backend/core/kernel/http/middleware_registration.py
# Feladat: A globális FastAPI middleware láncot állítja össze helyes sorrendben. Beköti a fallback rate limitet, CSRF-et, auth és tenant middleware-t, trusted hostot, observability middleware-eket, security headeröket és CORS-t. Core HTTP assembly elem, amely az app_factory részeként kapcsolja össze a security, tenant és observability rétegeket.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import os
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request

from core.kernel.config.config_loader import settings
from core.kernel.config.environment import is_deployed_env
from core.kernel.deps.facade import get_login_service, get_service, get_tenant_repository, get_token_service
from core.kernel.interface.keys import PLATFORM_DOMAIN_ROUTING_POLICY, PLATFORM_TENANT_LIFECYCLE_POLICY
from core.kernel.app.app_manifest import AppManifest
from core.kernel.http.error_payloads import build_error_payload, request_id_from_request
from core.kernel.http.correlation_id_middleware import CorrelationIdMiddleware
from core.kernel.http.request_timing_middleware import RequestTimingMiddleware
from core.kernel.security.csrf_middleware import CSRFMiddleware, csrf_disabled_by_env
from core.kernel.security.security_headers_middleware import SecurityHeadersMiddleware
from core.kernel.security.rate_limit import enforce_fallback_throttle
from core.modules.auth.middleware.auth_middleware import AuthMiddleware
from core.modules.tenant.middleware import TenantMiddleware


def _build_cors_origin_regex() -> str:
    base = re.escape(settings.tenant_base_domain)
    # Deployolt környezetben (staging/production) credentials mellett csak HTTPS origin engedett.
    scheme = "https" if is_deployed_env() else "https?"
    if settings.tenant_base_domain == "local":
        return rf"^{scheme}://(localhost|([a-z0-9][a-z0-9-]*\.)?{base})(:\d+)?$"
    return rf"^{scheme}://([a-z0-9][a-z0-9-]*\.)?{base}(:\d+)?$"


def register_middlewares(app: FastAPI, manifest: AppManifest) -> None:
    @app.middleware("http")
    async def fallback_endpoint_throttle(request: Request, call_next):
        allowed, _ = enforce_fallback_throttle(request)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content=build_error_payload(
                    status_code=429,
                    request_id=request_id_from_request(request),
                    code="RATE_LIMITED",
                    message="Too many requests. Please try again later.",
                    detail="Túl sok kérés. Próbáld újra később.",
                ),
            )
        return await call_next(request)

    app.add_middleware(SlowAPIMiddleware)
    if not csrf_disabled_by_env():
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
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID", "X-Correlation-ID"],
        expose_headers=["X-Request-ID", "X-Correlation-ID", "X-Response-Time-Ms", "X-Timing-Spans"],
    )


__all__ = ["register_middlewares"]
