# backend/core/modules/auth/router/auth_router.py
# Feladat: Az auth HTTP API FastAPI adaptere. CSRF token, login, refresh, logout, demo-login és current-user endpointokat köt a LoginService, RefreshService és LogoutService műveleteihez, miközben rate limitet, lokalizált hibákat, cookie kezelést és token allowlistet alkalmaz. Auth router réteg, üzleti logika nélkül.
# Sárközi Mihály - 2026.05.21

import logging
import os

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response

from core.modules.auth.domain.dto import LoginInput, LoginTwoFactorRequired
from core.modules.auth.domain.exceptions import TwoFactorEmailError, TwoFactorTooManyAttemptsError
from core.modules.auth.web.rate_limit.auth_limits import (
    check_login_burst,
    check_login_step1_email,
    check_login_step2_pending_token,
    register_failed_login_attempt,
)
from core.modules.auth.use_cases.refresh_result import RefreshFailed, RefreshFailReason, RefreshSuccess
from core.modules.auth.router.auth_response_builder import (
    build_token_response,
    cookie_max_age,
    tenant_auth_context,
)
from core.modules.auth.router.demo_login_handler import handle_demo_login
from core.modules.auth.router.requests import LoginRequest
from core.modules.auth.router.responses import TokenResponse, TwoFactorRequiredResponse
from core.modules.auth.use_cases import LoginService, LogoutService, RefreshService
from core.modules.users.domain.dto import User
from core.modules.users.router.responses import UserResponse
from core.kernel.deps.facade import (
    get_service,
    get_login_service,
    get_logout_service,
    get_refresh_service,
    get_token_service,
)
from core.kernel.http.tenant_dependencies import (
    OptionalTenantContextDep,
    RequiredTenantContextDep,
)
from core.kernel.http.responses import OperationStatusResponse
from core.kernel.config.config_loader import settings
from core.kernel.logging.observability import increment_metric, log_structured_event
from core.kernel.security.csrf import generate_csrf_token, set_csrf_cookie
from core.kernel.security.rate_limit import limiter, refresh_token_key
from core.modules.auth.web.dependencies.auth_dependencies import get_current_user, get_current_user_optional
from core.modules.auth.repository.token_allowlist import add as allowlist_add, remove_by_user as allowlist_remove_by_user
from core.modules.auth.repository.token_allowlist import TokenAllowlistUnavailableError
from core.modules.auth.service.token_service import TokenService
from core.kernel.security.cookie_policy import clear_refresh_cookie, set_refresh_cookie
from core.kernel.interface.keys import PLATFORM_ADMIN_SERVICE
from lang.messages import ErrorCode
from shared.presentation import LocalizedPresenterBase

router = APIRouter()
_presenter = LocalizedPresenterBase()
_log = logging.getLogger(__name__)


def _request_ip(request: Request) -> str | None:
    return getattr(request.client, "host", None) if request.client else None


def _ensure_not_banned_ip(request: Request) -> None:
    ip = _request_ip(request)
    if not ip:
        return
    try:
        svc = get_service(PLATFORM_ADMIN_SERVICE)
        if hasattr(svc, "is_ip_banned") and svc.is_ip_banned(ip):
            raise HTTPException(status_code=403, detail="IP address is temporarily blocked")
    except RuntimeError:
        return


# CSRF TOKEN kezelése
@router.get("/auth/csrf-token")
@limiter.limit("120/minute")
def get_csrf_token(request: Request, response: Response, tenant: OptionalTenantContextDep):
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
    _ensure_not_banned_ip(request)
    lang = _presenter.lang(request)

    if getattr(request.state, "user", None) is not None:
        raise HTTPException(status_code=409, detail=_presenter.detail_for_lang(ErrorCode.ALREADY_LOGGED_IN, lang))

    if getattr(req, "pending_token", None) and getattr(req, "two_factor_code", None):
        if not check_login_step2_pending_token(req.pending_token, tenant.slug):
            raise HTTPException(status_code=429, detail=_presenter.detail_for_lang(ErrorCode.AUTH_RATE_LIMIT, lang))
    elif getattr(req, "email", None):
        if not check_login_step1_email(req.email, tenant.slug):
            raise HTTPException(status_code=429, detail=_presenter.detail_for_lang(ErrorCode.AUTH_RATE_LIMIT, lang))
        if not check_login_burst(req.email, _request_ip(request), tenant.slug):
            increment_metric("auth.burst_block_total", 1.0, tags={"tenant": tenant.slug or "_"})
            raise HTTPException(status_code=429, detail=_presenter.detail_for_lang(ErrorCode.AUTH_RATE_LIMIT, lang))

    client_host = _request_ip(request)
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
    except ValueError as e:
        if str(e) == "authenticator_required_setup":
            raise HTTPException(
                status_code=403,
                detail="Admin és owner felhasználónak az Authenticator beállítása kötelező a belépéshez (próbaidőszakon kívül).",
            ) from e
        raise
    except Exception as e:
        _log.exception("auth login failed unexpectedly: %s", e)
        detail = _presenter.detail_for_lang(ErrorCode.LOGIN_ERROR, lang)
        raise HTTPException(status_code=500, detail=detail) from e

    if result is None:
        failure_count = register_failed_login_attempt(req.email or "", client_host, tenant.slug)
        failure_threshold = max(1, int(getattr(settings, "rate_limit_login_failure_ban_threshold", 16)))
        if failure_count >= failure_threshold and client_host:
            try:
                admin_svc = get_service(PLATFORM_ADMIN_SERVICE)
                if hasattr(admin_svc, "ban_ip"):
                    admin_svc.ban_ip(
                        ip=client_host,
                        reason="auth_login_bruteforce_detected",
                        expires_hours=max(1, int(getattr(settings, "rate_limit_login_failure_ban_hours", 2))),
                        admin_user_id=None,
                    )
                    increment_metric("auth.auto_ip_ban_total", 1.0, tags={"tenant": tenant.slug or "_"})
                    log_structured_event(
                        "core.auth",
                        "auth.auto_ip_ban",
                        tenant_slug=tenant.slug,
                        ip=client_host,
                        failure_count=failure_count,
                    )
            except Exception:
                _log.warning("Automatic IP ban failed after repeated login attempts.")
        raise HTTPException(status_code=401, detail=_presenter.detail_for_lang(ErrorCode.INVALID_CREDENTIALS, lang))

    if isinstance(result, LoginTwoFactorRequired):
        return TwoFactorRequiredResponse(
            pending_token=result.pending_token,
            challenge_type=getattr(result, "challenge_type", "email"),
        )

    try:
        return build_token_response(
            response=response,
            tenant=tenant,
            result=result,
            auto_login=getattr(req, "auto_login", False),
        )
    except TokenAllowlistUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        _log.exception("auth login token/cookie/allowlist response failed: %s", e)
        detail = _presenter.detail_for_lang(ErrorCode.LOGIN_ERROR, lang)
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
    _ensure_not_banned_ip(request)
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
    _ensure_not_banned_ip(request)
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

    try:
        allowlist_add(tenant.slug, user.id, result.access_jti)
    except TokenAllowlistUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
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
@router.post("/auth/logout", response_model=OperationStatusResponse)
@limiter.limit("30/minute")
def logout(
    request: Request,
    response: Response,
    tenant: RequiredTenantContextDep,
    user: User | None = Depends(get_current_user_optional),
    svc: LogoutService = Depends(get_logout_service),
    token_service: TokenService = Depends(get_token_service),
):
    _ensure_not_banned_ip(request)
    rt = request.cookies.get("refresh_token")
    ip = _request_ip(request)
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

    return OperationStatusResponse()


@router.get("/auth/authenticator/status")
@limiter.limit("60/minute")
def authenticator_status(
    request: Request,
    user: User = Depends(get_current_user),
    svc: LoginService = Depends(get_login_service),
):
    return svc.authenticator_status(user.id)


@router.post("/auth/authenticator/setup")
@limiter.limit("20/minute")
def authenticator_setup(
    request: Request,
    user: User = Depends(get_current_user),
    svc: LoginService = Depends(get_login_service),
):
    issuer = getattr(settings, "authenticator_issuer", "AIPLAZA")
    return svc.start_authenticator_setup(user.id, user.email, issuer=issuer)


@router.post("/auth/authenticator/confirm")
@limiter.limit("20/minute")
def authenticator_confirm(
    request: Request,
    body: dict = Body(...),
    user: User = Depends(get_current_user),
    svc: LoginService = Depends(get_login_service),
):
    code = str((body or {}).get("code", "")).strip()
    if not code:
        raise HTTPException(status_code=400, detail="Authenticator code is required")
    try:
        return svc.confirm_authenticator_setup(user.id, code)
    except ValueError as exc:
        if str(exc) == "authenticator_setup_not_started":
            raise HTTPException(status_code=400, detail="Authenticator setup was not started") from exc
        if str(exc) == "invalid_authenticator_code":
            raise HTTPException(status_code=400, detail="Invalid authenticator code") from exc
        raise HTTPException(status_code=400, detail="Authenticator setup error") from exc


@router.delete("/auth/authenticator")
@limiter.limit("20/minute")
def authenticator_disable(
    request: Request,
    user: User = Depends(get_current_user),
    svc: LoginService = Depends(get_login_service),
):
    svc.disable_authenticator(user.id)
    return {"enabled": False, "pending": False}
