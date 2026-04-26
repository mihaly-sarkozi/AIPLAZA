# Canonical rate limit middleware module location.

def _tenant_user_or_ip_key(request):
    """
    Rate limit kulcs: tenant + user vagy IP.
    """
    from slowapi.util import get_remote_address

    tenant = getattr(request.state, "tenant_slug", None) or ""
    payload = getattr(request.state, "user_token_payload", None)
    if payload and payload.get("sub"):
        return f"t:{tenant}:user:{payload['sub']}"
    addr = get_remote_address(request)
    return f"t:{tenant}:ip:{addr}"


def user_or_ip_key(request):
    """Régi kompatibilitás: user vagy IP (tenant nélkül)."""
    from slowapi.util import get_remote_address

    payload = getattr(request.state, "user_token_payload", None)
    if payload and payload.get("sub"):
        return f"user:{payload['sub']}"
    return f"ip:{get_remote_address(request)}"


# Ez a függvény a(z) storage_uri logikáját valósítja meg.
def _storage_uri():
    from core.kernel.config.config_loader import settings

    url = getattr(settings, "redis_url", None)
    if url and str(url).strip():
        return str(url).strip()
    return None


def get_limiter():
    from slowapi import Limiter

    _limiter_kwargs: dict = {"key_func": _tenant_user_or_ip_key}
    _storage = _storage_uri()
    if _storage:
        _limiter_kwargs["storage_uri"] = _storage
    return Limiter(**_limiter_kwargs)


class _LazyLimiterProxy:
    def __init__(self) -> None:
        self._instance = None

    def _get_instance(self):
        if self._instance is None:
            self._instance = get_limiter()
        return self._instance

    def __getattr__(self, name: str):
        return getattr(self._get_instance(), name)


limiter = _LazyLimiterProxy()


def refresh_token_key(request):
    """
    Rate limit kulcs refresh végponthoz: tenant + session.
    """
    from slowapi.util import get_remote_address

    tenant = getattr(request.state, "tenant_slug", None) or ""
    rt = request.cookies.get("refresh_token")
    if rt:
        return f"t:{tenant}:refresh:{rt}"
    return f"t:{tenant}:ip:{get_remote_address(request)}"
