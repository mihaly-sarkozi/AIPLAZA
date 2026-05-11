from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, Response
import logging

from core.capabilities.audit.const.audit_log_action_const import AuditLogAction
from core.capabilities.audit.service.audit_service import AuditService
from core.capabilities.auth.rate_limit.auth_limits import (
    check_login_burst,
    check_login_step1_email,
    register_failed_login_attempt,
)
from core.capabilities.auth.router.auth_response_builder import cookie_max_age
from core.kernel.config.config_loader import settings
from core.kernel.security.csrf import generate_csrf_token, set_platform_admin_csrf_cookie
from core.kernel.security.cookie_policy import (
    PLATFORM_ADMIN_REFRESH_COOKIE_NAME,
    clear_platform_admin_refresh_cookie,
    set_platform_admin_refresh_cookie,
)

from core.di import get_audit_service, get_service
from core.kernel.security.rate_limit import limiter
from core.kernel.logging.observability import increment_metric, log_structured_event
from core.platform.service_keys import PLATFORM_ADMIN_SERVICE
from core.platform.auth.token_allowlist import add as allowlist_add
from core.platform.auth.token_allowlist import is_allowed as allowlist_is_allowed
from core.platform.auth.token_allowlist import remove_by_user as allowlist_remove_by_user
from core.platform.auth.token_allowlist import TokenAllowlistUnavailableError
from core.platform_admin.models import PlatformAdminUserORM
from core.platform_admin.schemas import (
    PlatformAdminAckAlertResponse,
    PlatformAdminBanIpRequest,
    PlatformAdminBanIpResponse,
    PlatformAdminChangePasswordRequest,
    PlatformAdminDemoSignupGateResponse,
    PlatformAdminDemoSignupGateUpdateRequest,
    PlatformAdminLoginRequest,
    PlatformAdminLoginResponse,
    PlatformAdminStatisticsResponse,
    PlatformAdminSecurityMonitoringResponse,
    PlatformAdminTenantResponse,
    PlatformAdminProfileUpdateRequest,
    PlatformAdminUserResponse,
    PlatformAdminMfaStatusResponse,
    PlatformAdminMfaSetupResponse,
    PlatformAdminMfaConfirmRequest,
    PlatformAdminMfaConfirmResponse,
    PlatformAdminMfaDisableRequest,
)
from core.platform_admin.service import PlatformAdminService
from core.extensions.tenant.signup.abuse_controls import is_demo_signup_enabled, set_demo_signup_enabled

router = APIRouter(prefix="/platform-admin", tags=["platform-admin"])
logger = logging.getLogger(__name__)


def get_platform_admin_service() -> PlatformAdminService:
    return get_service(PLATFORM_ADMIN_SERVICE)


def _audit_log(audit: AuditService, action: AuditLogAction, **kwargs) -> None:  # type: ignore[no-untyped-def]
    try:
        audit.log(action, **kwargs)
    except Exception:
        logger.exception("Platform admin audit logging failed", extra={"action": str(action)})


@router.get("/auth/csrf-token")
@limiter.limit("120/minute")
def get_platform_admin_csrf_token(request: Request, response: Response):
    token = generate_csrf_token()
    set_platform_admin_csrf_cookie(
        response,
        token,
        secure=settings.cookie_secure,
        samesite=getattr(settings, "cookie_samesite", "lax"),
    )
    return {"csrf_token": token}


def current_platform_admin(
    authorization: str | None = Header(default=None),
    service: PlatformAdminService = Depends(get_platform_admin_service),
) -> PlatformAdminUserORM:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing platform admin token")
    token = authorization.split(" ", 1)[1].strip()
    payload = service.verify_access_payload(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid platform admin token")
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid platform admin token")
    if not allowlist_is_allowed(None, user_id, str(payload.get("jti") or "")):
        raise HTTPException(status_code=401, detail="Invalid platform admin token")
    user = service.resolve_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid platform admin token")
    return user


def _request_ip(request: Request) -> str | None:
    return getattr(request.client, "host", None) if request.client else None


def _ensure_platform_admin_ip_allowlist(request: Request) -> None:
    if not bool(getattr(settings, "platform_admin_ip_allowlist_enabled", False)):
        return
    allowed = {
        part.strip()
        for part in str(getattr(settings, "platform_admin_allowed_ips", "") or "").split(",")
        if part.strip()
    }
    if not allowed:
        raise HTTPException(status_code=503, detail="Platform admin IP allowlist is not configured")
    ip = _request_ip(request)
    if not ip or ip not in allowed:
        raise HTTPException(status_code=403, detail="Platform admin login is restricted for this IP")


def _ensure_not_banned_ip(request: Request, service: PlatformAdminService) -> None:
    ip = _request_ip(request)
    if service.is_ip_banned(ip):
        raise HTTPException(status_code=403, detail="IP address is temporarily blocked")


@router.post("/auth/login", response_model=PlatformAdminLoginResponse)
@limiter.limit("10/minute")
def login(
    request: Request,
    response: Response,
    body: PlatformAdminLoginRequest = Body(...),
    service: PlatformAdminService = Depends(get_platform_admin_service),
    audit: AuditService = Depends(get_audit_service),
):
    _ensure_platform_admin_ip_allowlist(request)
    _ensure_not_banned_ip(request, service)
    client_host = _request_ip(request)
    user_agent = request.headers.get("user-agent")
    if not check_login_step1_email(body.email, "__platform_admin__"):
        _audit_log(
            audit,
            AuditLogAction.PLATFORM_ADMIN_LOGIN_FAILED,
            actor_type="platform_admin",
            outcome="rate_limited",
            details={"email": body.email},
            ip=client_host,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=429, detail="Túl sok belépési kísérlet. Próbáld újra később.")
    if not check_login_burst(body.email, client_host, "__platform_admin__"):
        increment_metric("auth.burst_block_total", 1.0, tags={"tenant": "__platform_admin__"})
        raise HTTPException(status_code=429, detail="Túl sok belépési kísérlet. Próbáld újra később.")
    try:
        result = service.login(body.email, body.password, ip=client_host, ua=user_agent, mfa_code=body.mfa_code)
    except ValueError as exc:
        code = str(exc)
        if code == "platform_admin_mfa_setup_required":
            raise HTTPException(
                status_code=403,
                detail="Platform admin MFA setup required before login.",
            )
        if code == "platform_admin_mfa_invalid":
            _audit_log(
                audit,
                AuditLogAction.PLATFORM_ADMIN_LOGIN_FAILED,
                actor_type="platform_admin",
                details={"email": body.email, "reason": "mfa_invalid"},
                ip=client_host,
                user_agent=user_agent,
            )
            raise HTTPException(status_code=401, detail="Érvénytelen MFA kód.")
        if code == "platform_admin_mfa_locked":
            _audit_log(
                audit,
                AuditLogAction.PLATFORM_ADMIN_LOGIN_FAILED,
                actor_type="platform_admin",
                outcome="rate_limited",
                details={"email": body.email, "reason": "mfa_locked"},
                ip=client_host,
                user_agent=user_agent,
            )
            increment_metric("auth.burst_block_total", 1.0, tags={"tenant": "__platform_admin__"})
            raise HTTPException(status_code=429, detail="Túl sok hibás MFA próbálkozás. Próbáld újra később.")
        raise
    if not result:
        failure_count = register_failed_login_attempt(body.email, client_host, "__platform_admin__")
        failure_threshold = max(1, int(getattr(settings, "rate_limit_login_failure_ban_threshold", 16)))
        if failure_count >= failure_threshold and client_host:
            try:
                service.ban_ip(
                    ip=client_host,
                    reason="platform_admin_login_bruteforce_detected",
                    expires_hours=max(1, int(getattr(settings, "rate_limit_login_failure_ban_hours", 2))),
                    admin_user_id=None,
                )
                increment_metric("auth.auto_ip_ban_total", 1.0, tags={"tenant": "__platform_admin__"})
                log_structured_event(
                    "core.platform_admin.auth",
                    "platform_admin.auto_ip_ban",
                    ip=client_host,
                    failure_count=failure_count,
                )
            except Exception:
                logger.warning("Automatic platform-admin IP ban failed.")
        _audit_log(
            audit,
            AuditLogAction.PLATFORM_ADMIN_LOGIN_FAILED,
            actor_type="platform_admin",
            details={"email": body.email},
            ip=client_host,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=401, detail="Hibás email vagy jelszó")
    token, refresh_token, access_jti, user = result
    set_platform_admin_refresh_cookie(
        response,
        refresh_token,
        secure=settings.cookie_secure,
        samesite=getattr(settings, "cookie_samesite", "lax"),
        max_age=cookie_max_age(auto_login=True),
    )
    try:
        allowlist_add(None, user.id, access_jti)
    except TokenAllowlistUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    _audit_log(
        audit,
        AuditLogAction.PLATFORM_ADMIN_LOGIN_SUCCESS,
        user_id=user.id,
        actor_type="platform_admin",
        target_type="platform_admin",
        target_id=str(user.id),
        ip=client_host,
        user_agent=user_agent,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": service.user_to_response(user),
    }


@router.post("/auth/refresh", response_model=PlatformAdminLoginResponse)
@limiter.limit("20/5minute")
def refresh(
    request: Request,
    response: Response,
    service: PlatformAdminService = Depends(get_platform_admin_service),
    audit: AuditService = Depends(get_audit_service),
):
    _ensure_platform_admin_ip_allowlist(request)
    _ensure_not_banned_ip(request, service)
    client_host = _request_ip(request)
    user_agent = request.headers.get("user-agent")
    token = request.cookies.get(PLATFORM_ADMIN_REFRESH_COOKIE_NAME)
    if not token:
        _audit_log(
            audit,
            AuditLogAction.PLATFORM_ADMIN_REFRESH_FAILED,
            actor_type="platform_admin",
            details={"reason": "missing_refresh_cookie"},
            ip=client_host,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=401, detail="Missing refresh token")
    result = service.refresh(token, ip=client_host, ua=user_agent)
    if not result:
        clear_platform_admin_refresh_cookie(
            response,
            secure=settings.cookie_secure,
            samesite=getattr(settings, "cookie_samesite", "lax"),
        )
        _audit_log(
            audit,
            AuditLogAction.PLATFORM_ADMIN_REFRESH_FAILED,
            actor_type="platform_admin",
            details={"reason": "invalid_refresh_token"},
            ip=client_host,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    access_token, refresh_token, access_jti, user = result
    set_platform_admin_refresh_cookie(
        response,
        refresh_token,
        secure=settings.cookie_secure,
        samesite=getattr(settings, "cookie_samesite", "lax"),
        max_age=cookie_max_age(auto_login=True),
    )
    try:
        allowlist_add(None, user.id, access_jti)
    except TokenAllowlistUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    _audit_log(
        audit,
        AuditLogAction.PLATFORM_ADMIN_REFRESH,
        user_id=user.id,
        actor_type="platform_admin",
        target_type="platform_admin",
        target_id=str(user.id),
        ip=client_host,
        user_agent=user_agent,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": service.user_to_response(user),
    }


@router.post("/auth/logout")
@limiter.limit("20/minute")
def logout(
    request: Request,
    response: Response,
    service: PlatformAdminService = Depends(get_platform_admin_service),
    audit: AuditService = Depends(get_audit_service),
):
    _ensure_not_banned_ip(request, service)
    token = request.cookies.get(PLATFORM_ADMIN_REFRESH_COOKIE_NAME)
    client_host = getattr(request.client, "host", None) if request.client else None
    user_agent = request.headers.get("user-agent")
    user_id: int | None = None
    if token:
        payload = service.token_service.decode_ignore_exp(token)
        if payload and payload.get("sub") is not None:
            try:
                user_id = int(payload["sub"])
            except (TypeError, ValueError):
                user_id = None
    service.logout(token)
    if token:
        payload = service.token_service.decode_ignore_exp(token)
        if payload and payload.get("sub") is not None:
            try:
                allowlist_remove_by_user(None, int(payload["sub"]))
            except (TypeError, ValueError):
                pass
    _audit_log(
        audit,
        AuditLogAction.PLATFORM_ADMIN_LOGOUT,
        user_id=user_id,
        actor_type="platform_admin",
        target_type="platform_admin",
        target_id=str(user_id) if user_id is not None else None,
        ip=client_host,
        user_agent=user_agent,
    )
    clear_platform_admin_refresh_cookie(
        response,
        secure=settings.cookie_secure,
        samesite=getattr(settings, "cookie_samesite", "lax"),
    )
    return {"status": "ok"}


@router.get("/auth/me", response_model=PlatformAdminUserResponse)
@limiter.limit("60/minute")
def me(
    request: Request,
    service: PlatformAdminService = Depends(get_platform_admin_service),
    user: PlatformAdminUserORM = Depends(current_platform_admin),
):
    return service.user_to_response(user)


@router.get("/auth/mfa/status", response_model=PlatformAdminMfaStatusResponse)
@limiter.limit("60/minute")
def platform_admin_mfa_status(
    request: Request,
    service: PlatformAdminService = Depends(get_platform_admin_service),
    user: PlatformAdminUserORM = Depends(current_platform_admin),
):
    return service.mfa_status(user.id)


@router.post("/auth/mfa/setup", response_model=PlatformAdminMfaSetupResponse)
@limiter.limit("20/minute")
def platform_admin_mfa_setup(
    request: Request,
    service: PlatformAdminService = Depends(get_platform_admin_service),
    user: PlatformAdminUserORM = Depends(current_platform_admin),
):
    return service.start_mfa_setup(user.id)


@router.post("/auth/mfa/confirm", response_model=PlatformAdminMfaConfirmResponse)
@limiter.limit("20/minute")
def platform_admin_mfa_confirm(
    request: Request,
    body: PlatformAdminMfaConfirmRequest = Body(...),
    service: PlatformAdminService = Depends(get_platform_admin_service),
    user: PlatformAdminUserORM = Depends(current_platform_admin),
):
    try:
        return service.confirm_mfa_setup(user.id, code=body.code)
    except ValueError as exc:
        code = str(exc)
        if code == "mfa_setup_not_started":
            raise HTTPException(status_code=400, detail="MFA setup was not started")
        if code == "invalid_mfa_code":
            raise HTTPException(status_code=400, detail="Invalid MFA code")
        raise


@router.post("/auth/mfa/disable")
@limiter.limit("10/minute")
def platform_admin_mfa_disable(
    request: Request,
    body: PlatformAdminMfaDisableRequest = Body(...),
    service: PlatformAdminService = Depends(get_platform_admin_service),
    user: PlatformAdminUserORM = Depends(current_platform_admin),
):
    try:
        service.disable_mfa(user.id, password=body.password)
    except ValueError as exc:
        if str(exc) == "invalid_password":
            raise HTTPException(status_code=400, detail="Invalid password")
        raise
    return {"status": "ok"}


@router.patch("/auth/me", response_model=PlatformAdminUserResponse)
@limiter.limit("30/minute")
def update_profile(
    request: Request,
    body: PlatformAdminProfileUpdateRequest = Body(...),
    service: PlatformAdminService = Depends(get_platform_admin_service),
    user: PlatformAdminUserORM = Depends(current_platform_admin),
    audit: AuditService = Depends(get_audit_service),
):
    updated = service.update_profile(user.id, name=body.name)
    _audit_log(
        audit,
        AuditLogAction.PLATFORM_ADMIN_PROFILE_UPDATED,
        user_id=user.id,
        actor_type="platform_admin",
        target_type="platform_admin",
        target_id=str(user.id),
        details={"name_changed": body.name != user.name},
    )
    return service.user_to_response(updated)


@router.post("/auth/me/change-password")
@limiter.limit("10/minute")
def change_password(
    request: Request,
    body: PlatformAdminChangePasswordRequest = Body(...),
    service: PlatformAdminService = Depends(get_platform_admin_service),
    user: PlatformAdminUserORM = Depends(current_platform_admin),
    audit: AuditService = Depends(get_audit_service),
):
    try:
        service.change_password(user.id, current_password=body.current_password, new_password=body.new_password)
        _audit_log(
            audit,
            AuditLogAction.PLATFORM_ADMIN_PASSWORD_CHANGED,
            user_id=user.id,
            actor_type="platform_admin",
            target_type="platform_admin",
            target_id=str(user.id),
        )
        return {"status": "ok"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/tenants/active", response_model=list[PlatformAdminTenantResponse])
@limiter.limit("60/minute")
def list_active_tenants(
    request: Request,
    service: PlatformAdminService = Depends(get_platform_admin_service),
    _user: PlatformAdminUserORM = Depends(current_platform_admin),
):
    return service.list_active_tenants()


@router.get("/statistics/overview", response_model=PlatformAdminStatisticsResponse)
@limiter.limit("60/minute")
def platform_statistics_overview(
    request: Request,
    service: PlatformAdminService = Depends(get_platform_admin_service),
    user: PlatformAdminUserORM = Depends(current_platform_admin),
    audit: AuditService = Depends(get_audit_service),
):
    _audit_log(
        audit,
        AuditLogAction.PLATFORM_ADMIN_STATS_VIEWED,
        user_id=user.id,
        actor_type="platform_admin",
        target_type="platform_admin",
        target_id=str(user.id),
    )
    return service.get_statistics()


@router.get("/statistics/tenants/{tenant_id}")
@limiter.limit("60/minute")
def platform_tenant_statistics_detail(
    request: Request,
    tenant_id: int,
    service: PlatformAdminService = Depends(get_platform_admin_service),
    user: PlatformAdminUserORM = Depends(current_platform_admin),
    audit: AuditService = Depends(get_audit_service),
):
    try:
        _audit_log(
            audit,
            AuditLogAction.PLATFORM_ADMIN_TENANT_STATS_VIEWED,
            user_id=user.id,
            actor_type="platform_admin",
            target_type="tenant",
            target_id=str(tenant_id),
        )
        return service.get_tenant_statistics_detail(tenant_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Tenant not found")


@router.get("/monitoring/security", response_model=PlatformAdminSecurityMonitoringResponse)
@limiter.limit("60/minute")
def platform_security_monitoring(
    request: Request,
    service: PlatformAdminService = Depends(get_platform_admin_service),
    user: PlatformAdminUserORM = Depends(current_platform_admin),
    audit: AuditService = Depends(get_audit_service),
):
    _audit_log(
        audit,
        AuditLogAction.PLATFORM_ADMIN_STATS_VIEWED,
        user_id=user.id,
        actor_type="platform_admin",
        target_type="platform_admin",
        target_id=str(user.id),
        details={"section": "security_monitoring"},
    )
    return service.get_security_monitoring()


@router.get("/monitoring/security/demo-signups", response_model=PlatformAdminDemoSignupGateResponse)
@limiter.limit("60/minute")
def platform_security_demo_signup_gate(
    request: Request,
    user: PlatformAdminUserORM = Depends(current_platform_admin),
):
    return {"enabled": is_demo_signup_enabled(default_enabled=bool(getattr(settings, "demo_signups_enabled", True)))}


@router.patch("/monitoring/security/demo-signups", response_model=PlatformAdminDemoSignupGateResponse)
@limiter.limit("30/minute")
def platform_security_update_demo_signup_gate(
    request: Request,
    body: PlatformAdminDemoSignupGateUpdateRequest = Body(...),
    user: PlatformAdminUserORM = Depends(current_platform_admin),
    audit: AuditService = Depends(get_audit_service),
):
    try:
        set_demo_signup_enabled(bool(body.enabled))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    _audit_log(
        audit,
        AuditLogAction.PLATFORM_ADMIN_STATS_VIEWED,
        user_id=user.id,
        actor_type="platform_admin",
        target_type="platform_admin",
        target_id=str(user.id),
        details={"section": "demo_signup_gate", "enabled": bool(body.enabled)},
    )
    return {"enabled": is_demo_signup_enabled(default_enabled=bool(getattr(settings, "demo_signups_enabled", True)))}


@router.post("/monitoring/security/ban-ip", response_model=PlatformAdminBanIpResponse)
@limiter.limit("20/minute")
def platform_security_ban_ip(
    request: Request,
    body: PlatformAdminBanIpRequest = Body(...),
    service: PlatformAdminService = Depends(get_platform_admin_service),
    user: PlatformAdminUserORM = Depends(current_platform_admin),
    audit: AuditService = Depends(get_audit_service),
):
    try:
        result = service.ban_ip(
            ip=body.ip,
            reason=body.reason,
            expires_hours=body.expires_hours,
            admin_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _audit_log(
        audit,
        AuditLogAction.PLATFORM_ADMIN_SECURITY_IP_BANNED,
        user_id=user.id,
        actor_type="platform_admin",
        target_type="security_ip_ban",
        target_id=result["ip"],
        details={"reason": result.get("reason"), "expires_at": str(result.get("expires_at") or "")},
    )
    return result


@router.delete("/monitoring/security/ban-ip/{ip}")
@limiter.limit("20/minute")
def platform_security_unban_ip(
    request: Request,
    ip: str,
    service: PlatformAdminService = Depends(get_platform_admin_service),
    user: PlatformAdminUserORM = Depends(current_platform_admin),
    audit: AuditService = Depends(get_audit_service),
):
    try:
        service.release_ip_ban(ip, admin_user_id=user.id)
    except ValueError:
        raise HTTPException(status_code=404, detail="IP ban not found")
    _audit_log(
        audit,
        AuditLogAction.PLATFORM_ADMIN_SECURITY_IP_UNBANNED,
        user_id=user.id,
        actor_type="platform_admin",
        target_type="security_ip_ban",
        target_id=ip,
        details={"released": True},
    )
    return {"status": "ok"}


@router.get("/monitoring/security/alerts")
@limiter.limit("60/minute")
def platform_security_alerts(
    request: Request,
    service: PlatformAdminService = Depends(get_platform_admin_service),
    user: PlatformAdminUserORM = Depends(current_platform_admin),
):
    return {"alerts": service.list_security_alerts()}


@router.post("/monitoring/security/alerts/{alert_id}/ack", response_model=PlatformAdminAckAlertResponse)
@limiter.limit("30/minute")
def platform_security_ack_alert(
    request: Request,
    alert_id: int,
    service: PlatformAdminService = Depends(get_platform_admin_service),
    user: PlatformAdminUserORM = Depends(current_platform_admin),
    audit: AuditService = Depends(get_audit_service),
):
    try:
        row = service.acknowledge_security_alert(alert_id, admin_user_id=user.id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Alert not found")
    _audit_log(
        audit,
        AuditLogAction.PLATFORM_ADMIN_SECURITY_ALERT_ACK,
        user_id=user.id,
        actor_type="platform_admin",
        target_type="security_alert",
        target_id=str(alert_id),
        details={"status": row.get("status")},
    )
    return row

