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
from apps.core.timing import record_span
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
    """Cache: csak authhoz kell (password_hash soha ne kerüljön cache-be)."""
    return json.dumps({
        "id": user.id,
        "role": user.role,
        "is_active": user.is_active,
        "security_version": getattr(user, "security_version", 0),
        "preferred_locale": getattr(user, "preferred_locale", None),
        "preferred_theme": getattr(user, "preferred_theme", None),
    })


def _user_from_json(s: str) -> User | None:
    """Cache-ből User összerakása: csak cache-ben tárolt mezők; email/password_hash üres (nem tároljuk)."""
    try:
        d = json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None
    return User(
        id=d.get("id"),
        email="",
        password_hash="",
        is_active=bool(d.get("is_active", True)),
        role=d.get("role", "user"),
        created_at=datetime.now(timezone.utc),
        name=None,
        registration_completed_at=None,
        failed_login_attempts=0,
        preferred_locale=d.get("preferred_locale"),
        preferred_theme=d.get("preferred_theme"),
        security_version=d.get("security_version", 0),
    )


def invalidate_user_cache(tenant_slug: str | None, user_id: int) -> None:
    """Kitiltás/role változás után: központi cache-ből töröljük a usert."""
    get_cache().delete(user_cache_key(tenant_slug, user_id))


# Full vs light path (tudatos finomhangolás):
# - Full auth: DB/cache user fetch + security version check. Csak olyan végpontoknál, ahol TÉNYLEG kell: write, admin, settings, permission.
# - Light path: csak token claim + allowlist + role (payload); NINCS DB fetch. Gyorsabb, de role/revoke csak token lejáratakor érvényesül.
# Új prefixet csak akkor adj a light_paths-hoz, ha a route nem ír, nem admin/settings/permission érzékeny. docs/Auth_light_paths.md
_DEFAULT_LIGHT_PATHS: tuple[str, ...] = ("/api/chat",)


def _minimal_user_from_payload(payload: dict, user_id: int) -> User:
    """Token payload-ból minimál User (id, role, is_active=True); DB/cache load nélkül."""
    return User(
        id=user_id,
        email="",
        password_hash="",
        is_active=True,
        role=payload.get("role", "user"),
        created_at=datetime.now(timezone.utc),
        name=None,
        registration_completed_at=None,
        failed_login_attempts=0,
        preferred_locale=None,
        preferred_theme=None,
        security_version=payload.get("user_ver", 0),
    )


class AuthMiddleware:
    """ASGI: Bearer token → payload; allowlist; majd full user (DB/cache + version check) VAGY light path (csak payload → minimál user).
    light_paths: prefixek, ahol NINCS DB fetch (token+allowlist+role elég). Minden más route = full auth (write/admin/settings/permission)."""
    def __init__(
        self,
        app: ASGIApp,
        token_service: TokenService,
        login_service: LoginService,
        *,
        light_paths: tuple[str, ...] | None = None,
    ) -> None:
        self.app = app
        self.token_service = token_service
        self.login_service = login_service
        self.light_paths = light_paths if light_paths is not None else _DEFAULT_LIGHT_PATHS

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

    def _get_user_with_timing(self, tenant_slug: str | None, user_id: int) -> tuple[User | None, bool, float, float]:
        """Ugyanaz mint _get_user, de visszaad (user, cache_hit, cache_ms, db_ms) a hot-path méréshez."""
        t0 = time.monotonic()
        if not tenant_slug:
            user = self.login_service.user_repository.get_by_id(user_id)
            if user and not getattr(user, "is_active", True):
                return None, False, 0.0, (time.monotonic() - t0) * 1000
            return user, False, 0.0, (time.monotonic() - t0) * 1000
        cache = get_cache()
        key = user_cache_key(tenant_slug, user_id)
        raw = cache.get(key)
        cache_ms = (time.monotonic() - t0) * 1000
        if raw:
            user = _user_from_json(raw)
            if user and getattr(user, "is_active", True):
                return user, True, cache_ms, 0.0
            cache.delete(key)
        t1 = time.monotonic()
        user = self.login_service.user_repository.get_by_id(user_id)
        db_ms = (time.monotonic() - t1) * 1000
        if user and not getattr(user, "is_active", True):
            return None, False, cache_ms, db_ms
        if user:
            cache.set(key, _user_to_json(user), USER_TTL_SEC)
        return user, False, cache_ms, db_ms

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
                t0_tv = time.monotonic()
                loop = asyncio.get_event_loop()
                payload = await loop.run_in_executor(None, lambda: self.token_service.verify(token))
                record_span("token_verify", (time.monotonic() - t0_tv) * 1000)
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
            t0_al = time.monotonic()
            allowlist_ok = user_id and jti and allowlist_is_allowed(tenant_slug, int(user_id), jti)
            record_span("allowlist_check", (time.monotonic() - t0_al) * 1000)
            if allowlist_ok:
                uid = int(user_id)
                path = scope.get("path") or ""

                # Light path: token+allowlist+role elég, nincs DB fetch. Full auth: write/admin/settings/permission route-okra.
                if self.light_paths and any(path.startswith(prefix) for prefix in self.light_paths):
                    state["user"] = _minimal_user_from_payload(payload, uid)
                    state["auth_light"] = True
                    _log.info(
                        "auth_light_path",
                        extra={"path": path, "user_id": uid, "correlation_id": state.get("correlation_id")},
                    )
                else:
                    tenant_slug_for_fetch = tenant_slug

                    def _fetch_user() -> tuple[User | None, bool, float, float]:
                        if tenant_slug_for_fetch:
                            current_tenant_schema.set(tenant_slug_for_fetch)
                        try:
                            return self._get_user_with_timing(tenant_slug_for_fetch, uid)
                        finally:
                            current_tenant_schema.set(None)

                    t0 = time.monotonic()
                    loop = asyncio.get_event_loop()
                    user, cache_hit, cache_ms, db_ms = await loop.run_in_executor(None, _fetch_user)
                    elapsed = time.monotonic() - t0
                    record_span("user_cache_hit" if cache_hit else "user_cache_miss", cache_ms)
                    if db_ms > 0:
                        record_span("user_db_fetch", db_ms)
                    _timing(f"  -> auth user lookup user_id={uid} {elapsed:.3f}s")
                    if elapsed > 1.0:
                        _log.warning("auth user lookup slow: user_id=%s %.2fs", uid, elapsed)
                    token_user_ver = payload.get("user_ver", 0)
                    token_tenant_ver = payload.get("tenant_ver", 0)
                    current_user_ver = getattr(user, "security_version", 0) if user else 0
                    current_tenant_ver = state.get("tenant_security_version", 0)
                    if user and token_user_ver == current_user_ver and token_tenant_ver == current_tenant_ver:
                        state["user"] = user
                        state["auth_light"] = False
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
