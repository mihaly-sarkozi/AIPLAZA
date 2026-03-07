# apps/core/middleware/rate_limit_middleware.py
# Rate limit: slowapi Limiter, központi Redis store (horizontális skálázás).
# Kulcs: tenant + user vagy IP (tenant/user/IP dimenziók); policy = route-onkénti limit (X/minute).
# REDIS_URL beállítva → Redis; üres → in-memory (dev, egy instance).
# 2026.02.14 - Sárközi Mihály

from slowapi import Limiter
from slowapi.util import get_remote_address


def _tenant_user_or_ip_key(request):
    """
    Rate limit kulcs: tenant + user vagy IP (központi store-ban egyértelmű).
    tenant_slug a TenantMiddleware-ből (request.state.tenant_slug); user a token payload sub.
    Formátum: "t:{tenant}:user:{id}" vagy "t:{tenant}:ip:{addr}".
    """
    tenant = getattr(request.state, "tenant_slug", None) or ""
    payload = getattr(request.state, "user_token_payload", None)
    if payload and payload.get("sub"):
        return f"t:{tenant}:user:{payload['sub']}"
    addr = get_remote_address(request)
    return f"t:{tenant}:ip:{addr}"


def user_or_ip_key(request):
    """Régi kompatibilitás: user vagy IP (tenant nélkül); @limiter.limit(..., key_func) használja a _tenant_user_or_ip_key-t ahol kell."""
    payload = getattr(request.state, "user_token_payload", None)
    if payload and payload.get("sub"):
        return f"user:{payload['sub']}"
    return f"ip:{get_remote_address(request)}"


def _storage_uri():
    from config.settings import settings
    url = getattr(settings, "redis_url", None)
    if url and str(url).strip():
        return str(url).strip()
    return None


_limiter_kwargs: dict = {"key_func": _tenant_user_or_ip_key}
_storage = _storage_uri()
if _storage:
    _limiter_kwargs["storage_uri"] = _storage
limiter = Limiter(**_limiter_kwargs)


def refresh_token_key(request):
    """
    Rate limit kulcs refresh végponthoz: tenant + session (csak cookie; policy: refresh csak cookie).
    Limit: 20/5perc per session; központi store-ban tenant dimenzióval.
    """
    tenant = getattr(request.state, "tenant_slug", None) or ""
    rt = request.cookies.get("refresh_token")
    if rt:
        return f"t:{tenant}:refresh:{rt}"
    return f"t:{tenant}:ip:{get_remote_address(request)}"