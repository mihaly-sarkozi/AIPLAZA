# apps/core/middleware/auth_middleware.py 
# MIDDLEWARE - JWT ellenőrzés + user betöltés
# Minden kérésnél: ha van érvényes Bearer access token, dekódoljuk (user_token_payload),
# majd a user_id (sub) alapján DB-ből (vagy cache-ből) betöltjük a User-t.
# Rövid TTL cache csökkenti a DB terhelést. Sync DB hívás executorban (ne blokkolja az event loopot).
# 2026.03.07 - Sárközi Mihály

import asyncio
import contextvars
import logging
import sys
import threading
import time
from datetime import datetime, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from apps.core.security.token_service import TokenService
from apps.core.security.token_allowlist import is_allowed as allowlist_is_allowed
from apps.auth.application.services.login_service import LoginService

_USER_CACHE_TTL_SEC = 60
_user_cache: dict[tuple[str, int], tuple[object, float]] = {}
_user_cache_lock = threading.Lock()
_log = logging.getLogger(__name__)

def _ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
def _timing(msg: str):
    print(f"[TIME] {_ts()} {msg}", file=sys.stderr, flush=True)


def invalidate_user_cache(tenant_slug: str | None, user_id: int) -> None:
    """Kitiltás/role változás után: a middleware user cache-ből töröljük a usert."""
    with _user_cache_lock:
        _user_cache.pop((tenant_slug, user_id), None)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token_service: TokenService, login_service: LoginService):
        super().__init__(app)
        self.token_service = token_service
        self.login_service = login_service

    def _get_user(self, tenant_slug: str | None, user_id: int):
        if not tenant_slug:
            user = self.login_service.user_repository.get_by_id(user_id)
            if user and not getattr(user, "is_active", True):
                return None
            return user
        key = (tenant_slug, user_id)
        now = time.monotonic()
        with _user_cache_lock:
            if key in _user_cache:
                user, expires = _user_cache[key]
                if now < expires:
                    if not getattr(user, "is_active", True):
                        del _user_cache[key]
                        return None
                    return user
                del _user_cache[key]
        user = self.login_service.user_repository.get_by_id(user_id)
        if user and not getattr(user, "is_active", True):
            return None
        if user:
            with _user_cache_lock:
                _user_cache[key] = (user, now + _USER_CACHE_TTL_SEC)
        return user

    async def dispatch(self, request: Request, call_next):
        t0_mw = time.monotonic()
        _timing("MIDDLEWARE AuthMiddleware IN")
        token = None
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

        if token:
            try:
                payload = self.token_service.verify(token)
                request.state.user_token_payload = payload
            except Exception:
                request.state.user_token_payload = None
        else:
            request.state.user_token_payload = None

        payload = getattr(request.state, "user_token_payload", None)
        if payload and payload.get("typ") == "access":
            user_id = payload.get("sub")
            jti = payload.get("jti")
            tenant_slug = getattr(request.state, "tenant_slug", None)
            if user_id and jti and allowlist_is_allowed(tenant_slug, int(user_id), jti):
                uid = int(user_id)
                # Context (current_tenant_schema) nem látszik az executor szálban; így a session a jó sémát használja
                ctx = contextvars.copy_context()

                def _fetch_user():
                    return ctx.run(lambda: self._get_user(tenant_slug, uid))

                t0 = time.monotonic()
                loop = asyncio.get_event_loop()
                user = await loop.run_in_executor(None, _fetch_user)
                elapsed = time.monotonic() - t0
                _timing(f"  -> auth user lookup user_id={uid} {elapsed:.3f}s")
                if elapsed > 1.0:
                    _log.warning("auth user lookup slow: user_id=%s %.2fs", uid, elapsed)
                request.state.user = user
            else:
                # Token nincs az allowlistben (logout/törlés) → nem tekintjük bejelentkezettnek → 401
                request.state.user_token_payload = None
                request.state.user = None
        else:
            request.state.user = None

        out = await call_next(request)
        _timing(f"MIDDLEWARE AuthMiddleware OUT  {time.monotonic() - t0_mw:.3f}s")
        return out
