# Authentikációs API végpontok
# 2026.02.14 - Sárközi Mihály
#
# Felelősség: HTTP route-ok bekötése és kérés/válasz adaptálás.
# Üzleti logika → service réteg, token/cookie kezelés → auth_response_builder,
# demo-login validáció → demo_login_handler.

import logging
import os

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response

from core.capabilities.auth.dto import LoginInput, LoginTwoFactorRequired
from core.capabilities.auth.exceptions import TwoFactorEmailError, TwoFactorTooManyAttemptsError
from core.capabilities.auth.rate_limit.auth_limits import check_login_step1_email, check_login_step2_pending_token
from core.capabilities.auth.service.refresh_result import RefreshFailed, RefreshFailReason, RefreshSuccess
from core.capabilities.auth.router.auth_response_builder import (
    build_token_response,
    cookie_max_age,
    tenant_auth_context,
)
from core.capabilities.auth.router.demo_login_handler import handle_demo_login
from core.capabilities.auth.router.requests import LoginRequest
from core.capabilities.auth.router.responses import TokenResponse, TwoFactorRequiredResponse
from core.capabilities.auth.service import LoginService, LogoutService, RefreshService
from core.capabilities.users.dto import User
from core.capabilities.users.router.responses import UserResponse
from core.di import (
    OptionalTenantContextDep,
    RequiredTenantContextDep,
    get_login_service,
    get_logout_service,
    get_refresh_service,
    get_token_service,
)
from core.kernel.config.config_loader import settings
from core.kernel.security.csrf import generate_csrf_token, set_csrf_cookie
from core.kernel.security.rate_limit import limiter, refresh_token_key
from core.platform.auth.auth_dependencies import get_current_user_optional
from core.platform.auth.token_allowlist import add as allowlist_add, remove_by_user as allowlist_remove_by_user
from core.platform.auth.token_service import TokenService
from core.kernel.security.cookie_policy import clear_refresh_cookie, set_refresh_cookie
from lang.messages import ErrorCode
from shared.presentation import LocalizedPresenterBase

router = APIRouter()
_presenter = LocalizedPresenterBase()
_log = logging.getLogger(__name__)


# CSRF TOKEN kezelése
@router.get("/auth/csrf-token")
def get_csrf_token(response: Response, tenant: OptionalTenantContextDep):
    """Return CSRF token for double-submit; also set in cookie. No auth required."""
    token = generate_csrf_token()
    set_csrf_cookie(
        response,
        token,
        secure=settings.cookie_secure,
        samesite=getattr(settings, "cookie_samesite", "lax"),
    )
    return {"csrf_token": token}


# Felhasználó bejelentkezés
@router.post("/auth/login")
@limiter.limit(lambda: f"{settings.rate_limit_login_per_minute}/minute")
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    tenant: RequiredTenantContextDep,
    svc: LoginService = Depends(get_login_service),
):
    lang = _presenter.lang(request)

    if getattr(request.state, "user", None) is not None:
        raise HTTPException(status_code=409, detail=_presenter.detail_for_lang(ErrorCode.ALREADY_LOGGED_IN, lang))

    if getattr(req, "pending_token", None) and getattr(req, "two_factor_code", None):
        if not check_login_step2_pending_token(req.pending_token, tenant.slug):
            raise HTTPException(status_code=429, detail=_presenter.detail_for_lang(ErrorCode.AUTH_RATE_LIMIT, lang))
    elif getattr(req, "email", None):
        if not check_login_step1_email(req.email, tenant.slug):
            raise HTTPException(status_code=429, detail=_presenter.detail_for_lang(ErrorCode.AUTH_RATE_LIMIT, lang))

    client_host = getattr(request.client, "host", None) if request.client else None
    inp = LoginInput(
        email=req.email,
        password=req.password,
        pending_token=req.pending_token,
        two_factor_code=req.two_factor_code,
        ip=client_host,
        ua=request.headers.get("user-agent"),
        auto_login=getattr(req, "auto_login", False),
        tenant=tenant_auth_context(tenant),
    )
    try:
        result = svc.login(inp)
    except TwoFactorEmailError as e:
        raise HTTPException(status_code=503, detail=_presenter.detail_for_lang(e.error_code, lang))
    except TwoFactorTooManyAttemptsError:
        raise HTTPException(
            status_code=429,
            detail=_presenter.detail_for_lang(ErrorCode.TWO_FACTOR_TOO_MANY_ATTEMPTS, lang),
        )
    except Exception as e:
        _log.exception("auth login failed unexpectedly: %s", e)
        detail = _presenter.detail_for_lang(ErrorCode.LOGIN_ERROR, lang)
        if os.environ.get("APP_ENV", "dev").lower() != "prod":
            detail = {**detail, "debug_message": str(e)}
        raise HTTPException(status_code=500, detail=detail) from e

    if result is None:
        raise HTTPException(status_code=401, detail=_presenter.detail_for_lang(ErrorCode.INVALID_CREDENTIALS, lang))

    if isinstance(result, LoginTwoFactorRequired):
        return TwoFactorRequiredResponse(pending_token=result.pending_token)

    try:
        return build_token_response(
            response=response,
            tenant=tenant,
            result=result,
            auto_login=getattr(req, "auto_login", False),
        )
    except Exception as e:
        _log.exception("auth login token/cookie/allowlist response failed: %s", e)
        detail = _presenter.detail_for_lang(ErrorCode.LOGIN_ERROR, lang)
        if os.environ.get("APP_ENV", "dev").lower() != "prod":
            detail = {**detail, "debug_message": str(e)}
        raise HTTPException(status_code=500, detail=detail) from e


@router.post("/auth/demo-login", response_model=TokenResponse)
@limiter.limit("10/minute")
def demo_login(
    request: Request,
    response: Response,
    tenant: RequiredTenantContextDep,
    token: str = Body(..., embed=True),
    svc: LoginService = Depends(get_login_service),
    token_service: TokenService = Depends(get_token_service),
):
    return handle_demo_login(
        request=request,
        response=response,
        tenant=tenant,
        token=token,
        svc=svc,
        token_service=token_service,
    )


# Frissítő token
@router.post("/auth/refresh", response_model=TokenResponse)
@limiter.limit("20/5minute", key_func=refresh_token_key)
def refresh_tokens(
    request: Request,
    response: Response,
    tenant: RequiredTenantContextDep,
    svc: RefreshService = Depends(get_refresh_service),
    login_svc: LoginService = Depends(get_login_service),
):
    """Refresh token csak cookie-ból; új access + refresh cookie-t ad."""
    lang = _presenter.lang(request)
    rt = request.cookies.get("refresh_token")
    if not rt:
        raise HTTPException(status_code=401, detail=_presenter.detail_for_lang(ErrorCode.NO_REFRESH_TOKEN, lang))

    result = svc.refresh(
        rt,
        getattr(request.client, "host", None),
        request.headers.get("user-agent"),
        tenant=tenant_auth_context(tenant),
    )

    if isinstance(result, RefreshFailed):
        if result.reason == RefreshFailReason.RE_2FA_REQUIRED:
            raise HTTPException(status_code=401, detail=_presenter.detail_for_lang(ErrorCode.RE_2FA_REQUIRED, lang))
        if result.reason == RefreshFailReason.PERMISSIONS_CHANGED:
            raise HTTPException(status_code=401, detail=_presenter.detail_for_lang(ErrorCode.PERMISSIONS_CHANGED, lang))
        raise HTTPException(status_code=401, detail=_presenter.detail_for_lang(ErrorCode.INVALID_OR_REVOKED_REFRESH, lang))

    # result: RefreshSuccess
    user = result.user
    if user is None:
        user = login_svc.user_repository.get_by_id(
            int(svc.tokens.verify(result.refresh_token)["sub"])
        )

    allowlist_add(tenant.slug, user.id, result.access_jti)
    max_age = cookie_max_age(auto_login=result.auto_login)
    set_refresh_cookie(
        response,
        result.refresh_token,
        secure=settings.cookie_secure,
        samesite=getattr(settings, "cookie_samesite", "lax"),
        max_age=max_age,
    )

    return TokenResponse(
        access_token=result.access_token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            name=getattr(user, "name", None),
            is_active=getattr(user, "is_active", None),
            created_at=getattr(user, "created_at", None),
        ),
    )


# Kijelentkezés
@router.post("/auth/logout")
@limiter.limit("30/minute")
def logout(
    request: Request,
    response: Response,
    tenant: RequiredTenantContextDep,
    user: User | None = Depends(get_current_user_optional),
    svc: LogoutService = Depends(get_logout_service),
    token_service: TokenService = Depends(get_token_service),
):
    rt = request.cookies.get("refresh_token")
    ip = getattr(request.client, "host", None) if request.client else None
    ua = request.headers.get("user-agent")

    user_id: int | None = user.id if user else None
    if user_id is None and rt:
        payload = token_service.decode_ignore_exp(rt)
        if payload and payload.get("typ") == "refresh" and payload.get("sub"):
            user_id = int(payload["sub"])

    try:
        if rt:
            svc.logout(rt, ip=ip, ua=ua, tenant=tenant_auth_context(tenant))
    finally:
        if user_id is not None:
            allowlist_remove_by_user(tenant.slug, user_id)
        clear_refresh_cookie(
            response,
            secure=settings.cookie_secure,
            samesite=getattr(settings, "cookie_samesite", "lax"),
        )

    return {"ok": True}
