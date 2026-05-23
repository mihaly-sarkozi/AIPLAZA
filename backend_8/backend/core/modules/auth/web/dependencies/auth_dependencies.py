# backend/core/modules/auth/web/dependencies/auth_dependencies.py
# Feladat: Auth FastAPI és WebSocket dependency helperöket biztosít. A middleware által request.state-re tett usert ellenőrzi, permission/role dependency-ket épít az AuthorizationPolicy alapján, és WebSocket token validációt ad channel/chat használatra. Auth web adapter réteg, üzleti authorization döntés nélkül.
# Sárközi Mihály - 2026.05.21

import asyncio
from collections.abc import Iterable
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, Request

from core.modules.users.domain.dto import User
from core.kernel.deps.facade import get_permission_service, get_token_service
from core.kernel.logging.observability import increment_metric, log_structured_event
from core.modules.users.cache.user_cache import minimal_user_from_payload
from core.modules.auth.domain.authorization_policy import AuthorizationPolicy, normalize_values
from core.modules.auth.repository.token_allowlist import is_allowed as allowlist_is_allowed
from lang.messages import ErrorCode, get_message, lang_from_request


def get_current_user(request: Request) -> User:
    """
    Bejelentkezett, aktív user a middleware-ből (request.state.user).
    Ha nincs user vagy inaktív → 401.
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    if not getattr(user, "is_active", True):
        lang = lang_from_request(request)
        raise HTTPException(
            status_code=401,
            detail={"code": ErrorCode.PERMISSIONS_CHANGED.value, "message": get_message(ErrorCode.PERMISSIONS_CHANGED, lang)},
        )
    return user


def get_current_user_optional(request: Request) -> User | None:
    """
    User a middleware-ből, ha van érvényes token; különben None. Nem dob 401-et.
    """
    user = getattr(request.state, "user", None)
    if not user or not getattr(user, "is_active", True):
        return None
    return user


def _authorization_policy() -> AuthorizationPolicy:
    return AuthorizationPolicy(get_permission_service())


def require_permission(permission: str) -> Callable[[User], User]:
    def _dependency(user: User = Depends(get_current_user)) -> User:
        decision = _authorization_policy().ensure_permission(user, permission)
        if not decision.allowed:
            increment_metric("platform.auth.permission_denied.count", 1.0)
            log_structured_event(
                "core.authz",
                "permission_denied",
                level=30,
                permission=permission,
                user_id=getattr(user, "id", None),
                role=getattr(user, "role", None),
            )
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")
        return user

    _dependency.__name__ = f"require_permission__{permission.replace('.', '_')}"
    return _dependency


def require_any_permission(permissions: str | Iterable[str]) -> Callable[[User], User]:
    normalized = normalize_values(permissions)

    def _dependency(user: User = Depends(get_current_user)) -> User:
        decision = _authorization_policy().ensure_any_permission(user, normalized)
        if not decision.allowed:
            increment_metric("platform.auth.permission_denied.count", 1.0)
            log_structured_event(
                "core.authz",
                "permission_denied",
                level=30,
                required_permissions=list(normalized),
                user_id=getattr(user, "id", None),
                role=getattr(user, "role", None),
            )
            raise HTTPException(status_code=403, detail=f"Missing any permission: {', '.join(normalized)}")
        return user

    _dependency.__name__ = f"require_any_permission__{'__'.join(p.replace('.', '_') for p in normalized)}"
    return _dependency


def require_all_permissions(permissions: str | Iterable[str]) -> Callable[[User], User]:
    normalized = normalize_values(permissions)

    def _dependency(user: User = Depends(get_current_user)) -> User:
        decision = _authorization_policy().ensure_all_permissions(user, normalized)
        if not decision.allowed:
            increment_metric("platform.auth.permission_denied.count", 1.0)
            log_structured_event(
                "core.authz",
                "permission_denied",
                level=30,
                required_permissions=list(normalized),
                user_id=getattr(user, "id", None),
                role=getattr(user, "role", None),
            )
            raise HTTPException(status_code=403, detail=f"Missing required permissions: {', '.join(normalized)}")
        return user

    _dependency.__name__ = f"require_all_permissions__{'__'.join(p.replace('.', '_') for p in normalized)}"
    return _dependency


def require_role(roles: str | Iterable[str]) -> Callable[[User], User]:
    normalized = tuple(r.lower() for r in normalize_values(roles))

    def _dependency(user: User = Depends(get_current_user)) -> User:
        decision = _authorization_policy().ensure_role(user, normalized)
        if not decision.allowed:
            increment_metric("platform.auth.permission_denied.count", 1.0)
            log_structured_event(
                "core.authz",
                "permission_denied",
                level=30,
                required_roles=list(normalized),
                user_id=getattr(user, "id", None),
                role=getattr(user, "role", None),
            )
            raise HTTPException(status_code=403, detail=f"Missing required role: {', '.join(normalized)}")
        return user

    _dependency.__name__ = f"require_role__{'__'.join(r.replace('.', '_') for r in normalized)}"
    return _dependency


def has_permission(user: User | None, permission: str) -> bool:
    return get_permission_service().has_permission(user, permission)


async def validate_ws_token(token: str | None, tenant_slug: str | None = None) -> User | None:
    """WebSocket: token query param ellenőrzése. Visszaadja a minimál usert vagy None."""
    if not token or not token.strip():
        return None
    token = token.strip()
    token_service = get_token_service()
    loop = asyncio.get_event_loop()
    try:
        payload = await loop.run_in_executor(None, lambda: token_service.verify(token))
    except jwt.InvalidTokenError:
        return None
    if not payload or payload.get("typ") != "access":
        return None
    user_id = payload.get("sub")
    jti = payload.get("jti")
    if not user_id or not jti:
        return None
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    if not allowlist_is_allowed(tenant_slug, uid, jti):
        return None
    return minimal_user_from_payload(payload, uid)
