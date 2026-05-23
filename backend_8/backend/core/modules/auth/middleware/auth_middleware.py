# backend/core/modules/auth/middleware/auth_middleware.py
# Feladat: ASGI middleware, amely Bearer access tokenből request state auth adatokat épít. Ellenőrzi a JWT-t, token allowlistet, light path esetén minimál usert állít elő, egyébként cache/DB alapján feloldja a usert, és observability/timing adatokat köt a requesthez. Auth HTTP middleware, amelyet a kernel middleware lánc használ.
# Sárközi Mihály - 2026.05.21

import asyncio
import time

import jwt
from starlette.types import ASGIApp, Receive, Scope, Send

from core.modules.auth.use_cases import LoginService
from core.modules.users.domain.dto import User
from core.modules.tenant.context.tenant_context import current_tenant_schema
from core.kernel.logging.observability import bind_observability_context, reset_observability_context
from core.kernel.logging.request_timing import (
    log_timing_debug,
    log_timing_info,
    log_timing_warning,
    record_span,
)
from core.modules.users.cache.user_cache import (
    get_cached_user,
    invalidate_user_cache,  # re-exported so existing callers still work
    minimal_user_from_payload,
    set_cached_user,
)
from core.modules.auth.repository.token_allowlist import is_allowed as allowlist_is_allowed
from core.modules.auth.service.token_service import TokenService


def _get_header(scope: Scope, name: str) -> str | None:
    name_lower = name.encode().lower()
    for k, v in scope.get("headers", []):
        if k.lower() == name_lower:
            return v.decode("latin-1")
    return None


class AuthMiddleware:
    """ASGI middleware: Bearer token → User; allowlist; light-path optimization."""

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
        self.light_paths = light_paths or ()

    # ------------------------------------------------------------------
    # User resolution
    # ------------------------------------------------------------------

    def _fetch_user_from_db(self, tenant_slug: str | None, user_id: int) -> User | None:
        """Load user from the database; return None if inactive."""
        if tenant_slug:
            current_tenant_schema.set(tenant_slug)
        try:
            user = self.login_service.user_repository.get_by_id(user_id)
        finally:
            if tenant_slug:
                current_tenant_schema.set(None)
        if user and not getattr(user, "is_active", True):
            return None
        return user

    def _get_user_with_timing(
        self, tenant_slug: str | None, user_id: int
    ) -> tuple[User | None, bool, float, float]:
        """Return (user, cache_hit, cache_ms, db_ms)."""
        t0 = time.monotonic()

        if not tenant_slug:
            user = self._fetch_user_from_db(None, user_id)
            return user, False, 0.0, (time.monotonic() - t0) * 1000

        cached = get_cached_user(tenant_slug, user_id)
        cache_ms = (time.monotonic() - t0) * 1000
        if cached is not None:
            return cached, True, cache_ms, 0.0

        t1 = time.monotonic()
        user = self._fetch_user_from_db(tenant_slug, user_id)
        db_ms = (time.monotonic() - t1) * 1000
        if user:
            set_cached_user(tenant_slug, user)
        return user, False, cache_ms, db_ms

    def _resolve_request_user(
        self,
        token: str,
        tenant_slug: str | None,
        path: str,
    ) -> dict[str, object]:
        payload = self.token_service.verify(token)
        if not payload or payload.get("typ") != "access":
            return {"payload": None, "user": None, "auth_light": False}

        user_id = payload.get("sub")
        jti = payload.get("jti")
        if not user_id or not jti:
            return {"payload": None, "user": None, "auth_light": False}

        uid = int(user_id)
        if not allowlist_is_allowed(tenant_slug, uid, jti):
            return {"payload": None, "user": None, "auth_light": False}

        if self.light_paths and any(path.startswith(p) for p in self.light_paths):
            return {
                "payload": payload,
                "user": minimal_user_from_payload(payload, uid),
                "auth_light": True,
                "user_id": uid,
                "cache_hit": False,
                "cache_ms": 0.0,
                "db_ms": 0.0,
            }

        user, cache_hit, cache_ms, db_ms = self._get_user_with_timing(tenant_slug, uid)
        return {
            "payload": payload,
            "user": user,
            "auth_light": False,
            "user_id": uid,
            "cache_hit": cache_hit,
            "cache_ms": cache_ms,
            "db_ms": db_ms,
        }

    # ------------------------------------------------------------------
    # ASGI entry-point
    # ------------------------------------------------------------------

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        t0_mw = time.monotonic()
        state = scope.setdefault("state", {})
        state["auth_outcome"] = "anonymous"
        observability_token = None
        auth_header = _get_header(scope, "Authorization")
        token = None
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

        if token:
            try:
                tenant_slug = state.get("tenant_slug")
                path = scope.get("path") or ""
                t0_resolve = time.monotonic()
                loop = asyncio.get_event_loop()
                resolved = await loop.run_in_executor(
                    None,
                    lambda: self._resolve_request_user(token, tenant_slug, path),
                )
                elapsed_resolve_ms = (time.monotonic() - t0_resolve) * 1000
                payload = resolved.get("payload")
                state["user_token_payload"] = payload
                state["user"] = resolved.get("user")
                state["auth_light"] = bool(resolved.get("auth_light", False))
                state["auth_outcome"] = "authenticated_light" if state["auth_light"] else "authenticated"
                if resolved.get("user_id") is not None:
                    observability_token = bind_observability_context(user_id=int(resolved["user_id"]))
                record_span("auth_resolve", elapsed_resolve_ms)
                if payload and resolved.get("user_id") is not None and not state["auth_light"]:
                    cache_hit = bool(resolved.get("cache_hit", False))
                    cache_ms = float(resolved.get("cache_ms", 0.0) or 0.0)
                    db_ms = float(resolved.get("db_ms", 0.0) or 0.0)
                    record_span("user_cache_hit" if cache_hit else "user_cache_miss", cache_ms)
                    if db_ms > 0:
                        record_span("user_db_fetch", db_ms)
                    log_timing_debug(
                        "auth.middleware.user_lookup",
                        user_id=resolved.get("user_id"),
                        tenant_slug=tenant_slug,
                        elapsed_ms=round(elapsed_resolve_ms, 2),
                        cache_hit=cache_hit,
                        cache_ms=round(cache_ms, 2),
                        db_ms=round(db_ms, 2),
                    )
                    if elapsed_resolve_ms > 1000:
                        log_timing_warning(
                            "auth.user_lookup.slow",
                            user_id=resolved.get("user_id"),
                            tenant_slug=tenant_slug,
                            elapsed_ms=round(elapsed_resolve_ms, 2),
                        )
                elif payload and state["auth_light"]:
                    log_timing_info(
                        "auth.light_path",
                        path=path,
                        user_id=resolved.get("user_id"),
                        tenant_slug=tenant_slug,
                    )
            except jwt.InvalidTokenError:
                state["user_token_payload"] = None
                state["user"] = None
                state["auth_light"] = False
                state["auth_outcome"] = "invalid_token"
        else:
            state["user_token_payload"] = None
            state["user"] = None
            state["auth_light"] = False
            state["auth_outcome"] = "missing_token"

        payload = state.get("user_token_payload")
        user = state.get("user")
        if payload and payload.get("typ") == "access" and not state.get("auth_light"):
            token_user_ver = payload.get("user_ver", 0)
            token_tenant_ver = payload.get("tenant_ver", 0)
            current_user_ver = getattr(user, "security_version", 0) if user else 0
            tenant_snapshot = state.get("tenant_snapshot")
            current_tenant_ver = (
                getattr(tenant_snapshot, "security_version", None)
                or state.get("tenant_security_version", 0)
            )
            if not (user and token_user_ver == current_user_ver and token_tenant_ver == current_tenant_ver):
                state["user_token_payload"] = None
                state["user"] = None
                state["auth_outcome"] = "security_version_mismatch"

        record_span("auth_total", (time.monotonic() - t0_mw) * 1000)
        try:
            await self.app(scope, receive, send)
        finally:
            if observability_token is not None:
                reset_observability_context(observability_token)
            log_timing_debug(
                "auth.middleware.total",
                path=scope.get("path", ""),
                elapsed_ms=round((time.monotonic() - t0_mw) * 1000, 2),
                auth_outcome=state.get("auth_outcome"),
            )
