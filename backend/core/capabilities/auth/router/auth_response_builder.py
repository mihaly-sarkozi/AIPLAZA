"""Token response building helpers for auth routes.

Responsibility: given a successful login result, assemble the HTTP response:
set the refresh cookie, register the access JTI in the allowlist, and return
the TokenResponse body.  No routing, no business logic.
"""
from __future__ import annotations

from core.capabilities.auth.dto import LoginSuccess, TenantAuthContext
from core.capabilities.auth.router.responses import TokenResponse
from core.capabilities.users.router.responses import UserResponse
from core.kernel.config.config_loader import settings
from core.kernel.security.cookie_policy import set_refresh_cookie
from core.platform.auth.token_allowlist import add as allowlist_add

from fastapi.responses import Response


def tenant_auth_context(tenant) -> TenantAuthContext:
    """Extract the minimal TenantAuthContext from a resolved tenant snapshot."""
    return TenantAuthContext(
        tenant_id=tenant.tenant_id,
        slug=tenant.slug,
        correlation_id=tenant.correlation_id,
        security_version=tenant.security_version,
    )


def cookie_max_age(*, auto_login: bool) -> int:
    if auto_login:
        return int(settings.refresh_ttl_days * 24 * 3600)
    return int(getattr(settings, "refresh_ttl_session_hours", 24) * 3600)


def build_token_response(
    *,
    response: Response,
    tenant,
    result: LoginSuccess,
    auto_login: bool,
) -> TokenResponse:
    """Set refresh cookie + allowlist, return the body DTO."""
    set_refresh_cookie(
        response,
        result.refresh_token,
        secure=settings.cookie_secure,
        samesite=getattr(settings, "cookie_samesite", "lax"),
        max_age=cookie_max_age(auto_login=auto_login),
    )
    allowlist_add(tenant.slug, result.user.id, result.access_jti)
    return TokenResponse(
        access_token=result.access_token,
        user=UserResponse(
            id=result.user.id,
            email=result.user.email,
            role=result.user.role,
            name=getattr(result.user, "name", None),
            is_active=getattr(result.user, "is_active", None),
            created_at=getattr(result.user, "created_at", None),
        ),
    )
