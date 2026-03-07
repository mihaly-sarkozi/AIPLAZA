# apps/core/middleware/tenant_middleware.py
# MIDDLEWARE - Host → tenant (subdomain + domain→tenant cache + DB). ASGI, alacsony overhead.
# Cache: tenant, tenant_status, tenant_config, domain2tenant. scope["state"]: tenant_id, tenant_slug, tenant_security_version, tenant_status, tenant_config.
# 2026.03.07 - Sárközi Mihály

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from starlette.types import ASGIApp, Receive, Scope, Send

from apps.auth.ports import TenantRepositoryInterface
from apps.auth.domain.tenant import Tenant
from apps.auth.domain.tenant_status import TenantStatus
from apps.auth.domain.tenant_config import TenantConfig
from apps.core.db.tenant_context import current_tenant_schema
from apps.core.cache import (
    get_cache,
    tenant_cache_key,
    tenant_status_cache_key,
    tenant_config_cache_key,
    domain2tenant_cache_key,
    TENANT_TTL_SEC,
    TENANT_STATUS_TTL_SEC,
    TENANT_CONFIG_TTL_SEC,
    DOMAIN2TENANT_TTL_SEC,
)

_log = logging.getLogger(__name__)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def _timing(msg: str) -> None:
    print(f"[TIME] {_ts()} {msg}", file=__import__("sys").stderr, flush=True)


def _get_header(scope: Scope, name: str) -> str | None:
    name_lower = name.encode().lower()
    for k, v in scope.get("headers", []):
        if k.lower() == name_lower:
            return v.decode("latin-1")
    return None


def _tenant_to_json(tenant: Tenant) -> str:
    return json.dumps({
        "id": tenant.id,
        "slug": tenant.slug,
        "name": tenant.name,
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
        "security_version": getattr(tenant, "security_version", 0),
    })


def _tenant_from_json(s: str) -> Tenant:
    d = json.loads(s)
    created = d.get("created_at")
    if created:
        created = datetime.fromisoformat(created.replace("Z", "+00:00"))
    else:
        created = datetime.now(timezone.utc)
    return Tenant(
        id=d.get("id"),
        slug=d["slug"],
        name=d["name"],
        created_at=created,
        security_version=d.get("security_version", 0),
    )


def _status_to_json(st: TenantStatus) -> str:
    return json.dumps({"tenant_id": st.tenant_id, "slug": st.slug, "is_active": st.is_active, "suspended_reason": st.suspended_reason})


def _status_from_json(s: str) -> TenantStatus:
    d = json.loads(s)
    return TenantStatus(tenant_id=d["tenant_id"], slug=d["slug"], is_active=d.get("is_active", True), suspended_reason=d.get("suspended_reason"))


def _config_to_json(cfg: TenantConfig) -> str:
    return json.dumps({"tenant_id": cfg.tenant_id, "slug": cfg.slug, "package": cfg.package, "feature_flags": cfg.feature_flags, "limits": cfg.limits})


def _config_from_json(s: str) -> TenantConfig:
    d = json.loads(s)
    return TenantConfig(tenant_id=d["tenant_id"], slug=d["slug"], package=d.get("package", "free"), feature_flags=d.get("feature_flags") or {}, limits=d.get("limits") or {})


async def _send_json_response(send: Send, status: int, body: dict) -> None:
    body_bytes = json.dumps(body).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [[b"content-type", b"application/json"]],
    })
    await send({"type": "http.response.body", "body": body_bytes})


def warm_tenant_cache(slug: str, tenant_repo: TenantRepositoryInterface) -> None:
    """Induláskor meghívva: a slug tenant betöltése a központi cache-be."""
    tenant = tenant_repo.get_by_slug(slug)
    if tenant:
        get_cache().set(tenant_cache_key(slug), _tenant_to_json(tenant), TENANT_TTL_SEC)


def invalidate_tenant_cache(slug: str | None) -> None:
    """Tenant/security_version változás után: tenant + status + config cache törlése."""
    if not slug:
        return
    c = get_cache()
    c.delete(tenant_cache_key(slug))
    c.delete(tenant_status_cache_key(slug))
    c.delete(tenant_config_cache_key(slug))


def invalidate_domain2tenant_cache(host: str) -> None:
    """Domain→tenant mapping változás után (pl. domain regisztráció): domain cache törlése."""
    get_cache().delete(domain2tenant_cache_key(host.strip().lower()))


class TenantMiddleware:
    """ASGI: Host → slug (domain2tenant cache + subdomain + get_by_domain) → tenant + status + config cache."""

    def __init__(
        self,
        app: ASGIApp,
        tenant_repo: TenantRepositoryInterface,
        base_domain: str,
        localhost_tenant: str | None = "demo",
    ) -> None:
        self.app = app
        self._tenant_repo = tenant_repo
        self._base_domain = base_domain.strip().lower()
        self._localhost_tenant = localhost_tenant

    def _get_slug_for_host(self, host: str) -> str | None:
        """Host → slug: először domain2tenant cache, majd subdomain policy, végül DB (get_by_domain)."""
        cache = get_cache()
        d2t_key = domain2tenant_cache_key(host)
        raw = cache.get(d2t_key)
        if raw is not None:
            if raw == "":
                return None
            return raw
        slug = None
        if host.endswith("." + self._base_domain) or host == self._base_domain:
            slug = None if host == self._base_domain else host[: -len(self._base_domain) - 1].strip().lower() or None
        elif self._localhost_tenant and host in ("localhost", "127.0.0.1"):
            slug = self._localhost_tenant
        if slug is None:
            tenant = self._tenant_repo.get_by_domain(host)
            slug = tenant.slug if tenant else None
        cache.set(d2t_key, slug or "", DOMAIN2TENANT_TTL_SEC)
        return slug

    def _get_tenant(self, slug: str) -> Tenant | None:
        cache = get_cache()
        key = tenant_cache_key(slug)
        raw = cache.get(key)
        if raw:
            try:
                return _tenant_from_json(raw)
            except (json.JSONDecodeError, KeyError, TypeError):
                cache.delete(key)
        tenant = self._tenant_repo.get_by_slug(slug)
        if tenant:
            cache.set(key, _tenant_to_json(tenant), TENANT_TTL_SEC)
        return tenant

    def _get_tenant_status(self, slug: str) -> TenantStatus | None:
        cache = get_cache()
        key = tenant_status_cache_key(slug)
        raw = cache.get(key)
        if raw:
            try:
                return _status_from_json(raw)
            except (json.JSONDecodeError, KeyError, TypeError):
                cache.delete(key)
        st = self._tenant_repo.get_tenant_status(slug)
        if st:
            cache.set(key, _status_to_json(st), TENANT_STATUS_TTL_SEC)
        return st

    def _get_tenant_config(self, slug: str) -> TenantConfig | None:
        cache = get_cache()
        key = tenant_config_cache_key(slug)
        raw = cache.get(key)
        if raw:
            try:
                return _config_from_json(raw)
            except (json.JSONDecodeError, KeyError, TypeError):
                cache.delete(key)
        cfg = self._tenant_repo.get_tenant_config(slug)
        if cfg:
            cache.set(key, _config_to_json(cfg), TENANT_CONFIG_TTL_SEC)
        return cfg

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state = scope.setdefault("state", {})
        state["tenant_id"] = None
        state["tenant_slug"] = None
        state["tenant_security_version"] = 0
        state["tenant_status"] = None
        state["tenant_config"] = None
        token = current_tenant_schema.set(None)

        host = (_get_header(scope, "host") or "").split(":")[0].strip().lower()
        if not host:
            try:
                await self.app(scope, receive, send)
            finally:
                current_tenant_schema.reset(token)
            return

        t0 = time.monotonic()
        loop = asyncio.get_event_loop()
        slug = await loop.run_in_executor(None, lambda: self._get_slug_for_host(host))

        if slug:
            tenant = await loop.run_in_executor(None, lambda s=slug: self._get_tenant(s))
            elapsed = time.monotonic() - t0
            _timing(f"  -> tenant lookup slug={slug} {elapsed:.3f}s")
            if elapsed > 1.0:
                _log.warning("tenant lookup slow: slug=%s %.2fs", slug, elapsed)
            if not tenant or tenant.id is None:
                _timing(f"MIDDLEWARE TenantMiddleware OUT  {time.monotonic() - t0:.3f}s  (404)")
                await _send_json_response(
                    send, 404,
                    {"detail": "Ismeretlen vagy nem létező tenant. Ellenőrizd a címet (pl. demo.local, acme.local)."}
                )
                current_tenant_schema.reset(token)
                return
            status = await loop.run_in_executor(None, lambda s=slug: self._get_tenant_status(s))
            if status and not status.is_active:
                _timing(f"MIDDLEWARE TenantMiddleware OUT  (403 inactive)")
                await _send_json_response(
                    send, 403,
                    {"detail": "A tenant jelenleg nem aktív."}
                )
                current_tenant_schema.reset(token)
                return
            config = await loop.run_in_executor(None, lambda s=slug: self._get_tenant_config(s))
            state["tenant_id"] = tenant.id
            state["tenant_slug"] = tenant.slug
            state["tenant_security_version"] = getattr(tenant, "security_version", 0)
            state["tenant_status"] = status
            state["tenant_config"] = config
            current_tenant_schema.set(tenant.slug)
        elif scope.get("path", "").startswith("/api"):
            _timing(f"MIDDLEWARE TenantMiddleware OUT  (400)")
            await _send_json_response(
                send, 400,
                {"detail": "Tenant hiányzik. Használd a céges aldomaint (pl. http://demo.local:8001)."}
            )
            current_tenant_schema.reset(token)
            return

        try:
            await self.app(scope, receive, send)
        finally:
            current_tenant_schema.reset(token)
