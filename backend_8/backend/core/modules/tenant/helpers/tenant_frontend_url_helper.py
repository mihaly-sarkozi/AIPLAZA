# backend/core/modules/tenant/helpers/tenant_frontend_url_helper.py
# Feladat: Tenant frontend base URL képző helper. Request host és tenant context alapján állít elő tenant-aware frontend URL-t meghívókhoz és app linkekhez. HTTP/app integrációs segédfüggvény réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from fastapi import Request

from core.kernel.config.config_loader import settings


# Tenant frontend base URL kiszámítása a request és a tenant alapján
def tenant_frontend_base_url_for_slug(request: Request, slug: str) -> str:
    """Frontend base URL számítása adott tenant slughoz."""
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = f"{slug}.{settings.tenant_base_domain}"
    port = getattr(settings, "frontend_set_password_port", None)
    base = f"{scheme}://{host}"
    if port is not None:
        base = f"{base}:{port}"
    return base


def tenant_frontend_base_url_from_request(request: Request) -> str:
    """Frontend base URL számítása a request és az aktuális tenant alapján."""
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    snapshot = getattr(request.state, "tenant_snapshot", None)
    domain_info = getattr(request.state, "tenant_domain", None) or getattr(snapshot, "domain", None)
    tenant_slug = getattr(snapshot, "slug", None) or getattr(request.state, "tenant_slug", None)
    if tenant_slug:
        host = None
        if domain_info is not None:
            host = getattr(domain_info, "request_host", None) or getattr(domain_info, "resolved_host", None)
        host = (host or request.url.hostname or "").strip().lower()
        if host:
            port = getattr(settings, "frontend_set_password_port", None)
            base = f"{scheme}://{host}"
            if port is not None:
                base = f"{base}:{port}"
            return base
        return tenant_frontend_base_url_for_slug(request, tenant_slug)

    if getattr(settings, "frontend_base_url", ""):
        return str(settings.frontend_base_url).rstrip("/")

    hostname = request.url.hostname
    port = getattr(settings, "frontend_set_password_port", None)
    if port is not None:
        return f"{scheme}://{hostname}:{port}"
    return f"{scheme}://{hostname}"
