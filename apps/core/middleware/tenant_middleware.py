# apps/core/middleware/tenant_middleware.py 
# MIDDLEWARE - Subdomain → tenant (séma = slug)
# Host → slug. Ha van slug, kötelező hogy létezzen a tenant (public.tenants), különben 404.
# request.state.tenant_id, tenant_slug + current_tenant_schema (search_path) beállítva.
# Rövid TTL cache: ne legyen DB round-trip minden kérésnél (stalled / TTFB javítás).
# Sync DB hívás executorban, ne blokkolja az event loopot (TTFB javítás).
# 2026.03.07 - Sárközi Mihály

import asyncio
import logging
import sys
import threading
import time
from datetime import datetime, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from apps.auth.ports import TenantRepositoryInterface
from apps.auth.domain.tenant import Tenant
from apps.core.db.tenant_context import current_tenant_schema

_TENANT_CACHE_TTL_SEC = 60
_tenant_cache: dict[str, tuple[Tenant, float]] = {}
_tenant_cache_lock = threading.Lock()
_log = logging.getLogger(__name__)

def _ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
def _timing(msg: str):
    print(f"[TIME] {_ts()} {msg}", file=sys.stderr, flush=True)


def warm_tenant_cache(slug: str, tenant_repo: TenantRepositoryInterface) -> None:
    """Induláskor meghívva: a slug tenant betöltése a cache-be, így az első /me csak user DB-t fizet."""
    now = time.monotonic()
    tenant = tenant_repo.get_by_slug(slug)
    if tenant:
        with _tenant_cache_lock:
            _tenant_cache[slug] = (tenant, now + _TENANT_CACHE_TTL_SEC)


class TenantMiddleware(BaseHTTPMiddleware):
    """Host → slug → tenant kötelező; ha nincs ilyen tenant → 404. Séma = slug (search_path)."""

    def __init__(self, app, tenant_repo: TenantRepositoryInterface, base_domain: str, localhost_tenant: str | None = "demo"):
        super().__init__(app)
        self._tenant_repo = tenant_repo
        self._base_domain = base_domain.strip().lower()
        self._localhost_tenant = localhost_tenant  # dev: localhost → ezt a slug-ot használjuk

    def _get_tenant(self, slug: str) -> Tenant | None:
        now = time.monotonic()
        with _tenant_cache_lock:
            if slug in _tenant_cache:
                tenant, expires = _tenant_cache[slug]
                if now < expires:
                    return tenant
                del _tenant_cache[slug]
        tenant = self._tenant_repo.get_by_slug(slug)
        if tenant:
            with _tenant_cache_lock:
                _tenant_cache[slug] = (tenant, now + _TENANT_CACHE_TTL_SEC)
        return tenant

    async def dispatch(self, request: Request, call_next):
        t0_mw = time.monotonic()
        _timing("MIDDLEWARE TenantMiddleware IN")
        request.state.tenant_id = None
        request.state.tenant_slug = None
        token = current_tenant_schema.set(None)  # reset; restore in finally

        host = (request.headers.get("host") or "").split(":")[0].strip().lower()
        if not host:
            try:
                out = await call_next(request)
                _timing(f"MIDDLEWARE TenantMiddleware OUT  {time.monotonic() - t0_mw:.3f}s")
                return out
            finally:
                current_tenant_schema.reset(token)

        if host.endswith("." + self._base_domain) or host == self._base_domain:
            slug = None if host == self._base_domain else host[: -len(self._base_domain) - 1].strip().lower() or None
        elif self._localhost_tenant and host in ("localhost", "127.0.0.1"):
            slug = self._localhost_tenant
        else:
            slug = None

        if slug:
            t0 = time.monotonic()
            loop = asyncio.get_event_loop()
            tenant = await loop.run_in_executor(None, lambda s=slug: self._get_tenant(s))
            elapsed = time.monotonic() - t0
            _timing(f"  -> tenant lookup slug={slug} {elapsed:.3f}s")
            if elapsed > 1.0:
                _log.warning("tenant lookup slow: slug=%s %.2fs", slug, elapsed)
            if not tenant or tenant.id is None:
                _timing(f"MIDDLEWARE TenantMiddleware OUT  {time.monotonic() - t0_mw:.3f}s  (404)")
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Ismeretlen vagy nem létező tenant. Ellenőrizd a címet (pl. demo.local, acme.local)."}
                )
            request.state.tenant_id = tenant.id
            request.state.tenant_slug = tenant.slug
            current_tenant_schema.set(tenant.slug)
        elif request.url.path.startswith("/api"):
            _timing(f"MIDDLEWARE TenantMiddleware OUT  {time.monotonic() - t0_mw:.3f}s  (400)")
            return JSONResponse(
                status_code=400,
                content={"detail": "Tenant hiányzik. Használd a céges aldomaint (pl. http://demo.local:8001)."}
            )

        try:
            out = await call_next(request)
            _timing(f"MIDDLEWARE TenantMiddleware OUT  {time.monotonic() - t0_mw:.3f}s")
            return out
        finally:
            current_tenant_schema.reset(token)
