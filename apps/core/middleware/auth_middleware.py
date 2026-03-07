# apps/core/middleware/auth_middleware.py
# JWT ellenőrzés + user betöltés. ASGI – alacsonyabb overhead; scope.state.user / user_token_payload.
# Cache: központi (Redis/memory). 2026.03.07 - Sárközi Mihály

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from starlette.types import ASGIApp, Receive, Scope, Send

from apps.core.security.token_service import TokenService
from apps.core.security.token_allowlist import is_allowed as allowlist_is_allowed
from apps.auth.application.services.login_service import LoginService
from apps.core.cache import get_cache, user_cache_key, USER_TTL_SEC
from apps.core.db.tenant_context import current_tenant_schema
from apps.users.domain.user import User

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


def _user_to_json(user: User) -> str:
    def _dt(d):
        return d.isoformat() if d else None
    return json.dumps({
        "id": user.id,
        "email": user.email,
        "password_hash": user.password_hash,
        "is_active": user.is_active,
        "role": user.role,
        "created_at": _dt(user.created_at),
        "name": user.name,
        "registration_completed_at": _dt(getattr(user, "registration_completed_at", None)),
        "failed_login_attempts": getattr(user, "failed_login_attempts", 0),
        "preferred_locale": getattr(user, "preferred_locale", None),
        "preferred_theme": getattr(user, "preferred_theme", None),
        "security_version": getattr(user, "security_version", 0),
    })


def _user_from_json(s: str) -> User | None:
    try:
        d = json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None
    def _parse_dt(v):
        if not v:
            return None
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    created = _parse_dt(d.get("created_at")) or datetime.now(timezone.utc)
    return User(
        id=d.get("id"),
        email=d.get("email", ""),
        password_hash=d.get("password_hash", ""),
        is_active=bool(d.get("is_active", True)),
        role=d.get("role", "user"),
        created_at=created,
        name=d.get("name"),
        registration_completed_at=_parse_dt(d.get("registration_completed_at")),
        failed_login_attempts=d.get("failed_login_attempts", 0),
        preferred_locale=d.get("preferred_locale"),
        preferred_theme=d.get("preferred_theme"),
        security_version=d.get("security_version", 0),
    )


def invalidate_user_cache(tenant_slug: str | None, user_id: int) -> None:
    """Kitiltás/role változás után: központi cache-ből töröljük a usert."""
    get_cache().delete(user_cache_key(tenant_slug, user_id))


class AuthMiddleware:
    """ASGI: Bearer token → payload; access token + allowlist → user betöltés; scope.state.user, user_token_payload."""

    def __init__(self, app: ASGIApp, token_service: TokenService, login_service: LoginService) -> None:
        self.app = app
        self.token_service = token_service
        self.login_service = login_service

    def _get_user(self, tenant_slug: str | None, user_id: int) -> User | None:
        if not tenant_slug:
            user = self.login_service.user_repository.get_by_id(user_id)
            if user and not getattr(user, "is_active", True):
                return None
            return user
        cache = get_cache()
        key = user_cache_key(tenant_slug, user_id)
        raw = cache.get(key)
        if raw:
            user = _user_from_json(raw)
            if user and getattr(user, "is_active", True):
                return user
            cache.delete(key)
        user = self.login_service.user_repository.get_by_id(user_id)
        if user and not getattr(user, "is_active", True):
            return None
        if user:
            cache.set(key, _user_to_json(user), USER_TTL_SEC)
        return user

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        t0_mw = time.monotonic()
        _timing("MIDDLEWARE AuthMiddleware IN")
        state = scope.setdefault("state", {})
        auth_header = _get_header(scope, "Authorization")
        token = None
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

        if token:
            try:
                loop = asyncio.get_event_loop()
                payload = await loop.run_in_executor(None, lambda: self.token_service.verify(token))
                state["user_token_payload"] = payload
            except Exception:
                state["user_token_payload"] = None
        else:
            state["user_token_payload"] = None

        payload = state.get("user_token_payload")
        if payload and payload.get("typ") == "access":
            user_id = payload.get("sub")
            jti = payload.get("jti")
            tenant_slug = state.get("tenant_slug")
            if user_id and jti and allowlist_is_allowed(tenant_slug, int(user_id), jti):
                uid = int(user_id)
                tenant_slug_for_fetch = tenant_slug

                def _fetch_user() -> User | None:
                    if tenant_slug_for_fetch:
                        current_tenant_schema.set(tenant_slug_for_fetch)
                    try:
                        return self._get_user(tenant_slug_for_fetch, uid)
                    finally:
                        current_tenant_schema.set(None)

                t0 = time.monotonic()
                loop = asyncio.get_event_loop()
                user = await loop.run_in_executor(None, _fetch_user)
                elapsed = time.monotonic() - t0
                _timing(f"  -> auth user lookup user_id={uid} {elapsed:.3f}s")
                if elapsed > 1.0:
                    _log.warning("auth user lookup slow: user_id=%s %.2fs", uid, elapsed)
                token_user_ver = payload.get("user_ver", 0)
                token_tenant_ver = payload.get("tenant_ver", 0)
                current_user_ver = getattr(user, "security_version", 0) if user else 0
                current_tenant_ver = state.get("tenant_security_version", 0)
                if user and token_user_ver == current_user_ver and token_tenant_ver == current_tenant_ver:
                    state["user"] = user
                else:
                    state["user_token_payload"] = None
                    state["user"] = None
            else:
                state["user_token_payload"] = None
                state["user"] = None
        else:
            state["user"] = None

        await self.app(scope, receive, send)
        _timing(f"MIDDLEWARE AuthMiddleware OUT  {time.monotonic() - t0_mw:.3f}s")
