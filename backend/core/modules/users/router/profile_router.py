# backend/core/modules/users/router/profile_router.py
# Feladat: A self-service profile és auth/me FastAPI adaptere. Aktuális user lekérdezés, profile update, password change, forgot password, initial password és demo unsubscribe endpointokat köt service-ekhez. Users profile/auth boundary router.
# Sárközi Mihály - 2026.05.21

"""Profile and self-service routes.

Responsibility: HTTP endpoints for the currently authenticated user
(/auth/me, change-password, set-initial-password, demo-unsubscribe).
No admin / user-management logic here.
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response

from core.modules.auth.router.auth_response_builder import build_token_response, tenant_auth_context
from core.modules.auth.router.responses.token_response import TokenResponse
from core.modules.auth.use_cases.login_service import LoginService
from core.modules.users.dependencies import get_user_profile_service, get_user_service
from core.modules.users.domain.dto import User
from core.modules.users.domain.policies.profile_policy import tenant_demo_mode_enabled
from core.modules.users.router.requests.change_password_request import ChangePasswordRequest
from core.modules.users.router.requests.demo_unsubscribe_request import DemoUnsubscribeRequest
from core.modules.users.router.requests.forgot_password_request import ForgotPasswordRequest
from core.modules.users.router.requests.set_initial_password_request import SetInitialPasswordRequest
from core.modules.users.router.requests.update_me_request import UpdateMeRequest
from core.modules.users.service import UserService
from core.modules.users.service.profile_service import UserProfileService
from core.kernel.deps.facade import get_login_service, get_service
from core.kernel.http.responses import OperationStatusResponse
from core.kernel.http.tenant_dependencies import OptionalTenantContextDep, RequiredTenantContextDep
from core.modules.tenant.dependencies import get_tenant_signup_service
from core.modules.tenant.helpers.tenant_frontend_url_helper import tenant_frontend_base_url_from_request
from core.modules.tenant.service import TenantSignupService
from core.modules.users.cache.user_cache import invalidate_user_cache
from core.kernel.security.rate_limit import limiter
from core.modules.auth.web.dependencies.auth_dependencies import get_current_user
from core.modules.auth.repository.token_allowlist import remove_by_user as allowlist_remove_by_user
from core.kernel.interface.keys import PLATFORM_TENANT_USAGE_SERVICE
from lang.messages import ErrorCode
from shared.presentation import LocalizedPresenterBase

router = APIRouter()
_presenter = LocalizedPresenterBase()


def _request_ip(request: Request) -> str | None:
    return getattr(request.client, "host", None) if request.client else None


@router.get("/auth/me")
def me(
    tenant: RequiredTenantContextDep,
    user: User = Depends(get_current_user),
    profile_service: UserProfileService = Depends(get_user_profile_service),
):
    usage_service = None
    try:
        usage_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
    except Exception:
        usage_service = None
    return profile_service.get_me(user=user, tenant=tenant, training_status_reader=usage_service)


@router.get("/auth/default-settings")
def default_settings(
    _tenant: OptionalTenantContextDep,
    profile_service: UserProfileService = Depends(get_user_profile_service),
):
    return profile_service.get_default_settings()


@router.post("/auth/confirm-email", response_model=OperationStatusResponse)
@limiter.limit("10/minute")
def confirm_email_change(
    request: Request,
    tenant: RequiredTenantContextDep,
    token: str = "",
    profile_service: UserProfileService = Depends(get_user_profile_service),
):
    try:
        user = profile_service.confirm_email_change(token=token)
    except ValueError as exc:
        code = str(exc)
        status_code = 410 if code == "expired_email_change_token" else 400
        raise HTTPException(status_code=status_code, detail={"code": code, "message": code})
    invalidate_user_cache(tenant.slug, user.id)
    allowlist_remove_by_user(tenant.slug or "", user.id)
    return OperationStatusResponse(message="Email cím megerősítve. Jelentkezz be az új email címmel.")


@router.patch("/auth/me")
def update_me(
    tenant: RequiredTenantContextDep,
    body: UpdateMeRequest = Body(default=UpdateMeRequest()),
    user: User = Depends(get_current_user),
    profile_service: UserProfileService = Depends(get_user_profile_service),
):
    result = profile_service.update_me(
        user=user,
        name=body.name,
        preferred_locale=body.preferred_locale,
        preferred_theme=body.preferred_theme,
        updated_by=user.id,
    )
    invalidate_user_cache(tenant.slug, user.id)
    return result


@router.post("/auth/forgot-password", response_model=OperationStatusResponse)
@limiter.limit("10/minute")
def forgot_password(
    request: Request,
    tenant: RequiredTenantContextDep,
    svc: UserService = Depends(get_user_service),
    body: ForgotPasswordRequest = Body(...),
):
    base_url = tenant_frontend_base_url_from_request(request)
    svc.forgot_password(body.email.strip(), request_base_url=base_url)
    return OperationStatusResponse()


@router.post("/auth/me/change-password", response_model=OperationStatusResponse)
@limiter.limit("10/minute")
def change_password(
    request: Request,
    tenant: RequiredTenantContextDep,
    user: User = Depends(get_current_user),
    svc: UserService = Depends(get_user_service),
    body: ChangePasswordRequest = Body(...),
):
    lang = _presenter.lang(request)
    try:
        svc.change_password(
            user_id=user.id,
            current_password=body.current_password,
            new_password=body.new_password,
            ip=_request_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except ValueError as exc:
        if str(exc) == "current_password_wrong":
            raise HTTPException(status_code=400, detail=_presenter.detail_for_lang(ErrorCode.CURRENT_PASSWORD_WRONG, lang))
        if str(exc) == "credentials_password_not_set":
            raise HTTPException(
                status_code=400,
                detail=_presenter.detail_for_lang(ErrorCode.CREDENTIALS_PASSWORD_NOT_SET, lang),
            )
        raise HTTPException(status_code=400, detail=str(exc))
    return OperationStatusResponse()


@router.post("/auth/me/set-initial-password", response_model=TokenResponse)
@limiter.limit("10/minute")
def set_initial_password(
    request: Request,
    response: Response,
    tenant: RequiredTenantContextDep,
    user: User = Depends(get_current_user),
    svc: UserService = Depends(get_user_service),
    login_svc: LoginService = Depends(get_login_service),
    body: SetInitialPasswordRequest = Body(...),
):
    """Demo: első saját jelszó; régi jelszó nem kell."""
    lang = _presenter.lang(request)
    tenant_demo_mode = tenant_demo_mode_enabled(tenant)
    if not tenant_demo_mode:
        raise HTTPException(status_code=403, detail=_presenter.detail_for_lang(ErrorCode.NOT_DEMO_TENANT, lang))
    try:
        svc.set_initial_password_demo(
            user_id=user.id,
            new_password=body.new_password,
            tenant_demo_mode=tenant_demo_mode,
        )
    except ValueError as exc:
        msg = str(exc)
        if msg == "credentials_already_set":
            raise HTTPException(status_code=400, detail=_presenter.detail_for_lang(ErrorCode.CREDENTIALS_ALREADY_SET, lang))
        if msg == "not_demo_tenant":
            raise HTTPException(status_code=403, detail=_presenter.detail_for_lang(ErrorCode.NOT_DEMO_TENANT, lang))
        if msg == "user_not_found":
            raise HTTPException(status_code=404, detail="User not found")
        raise HTTPException(status_code=400, detail=msg)
    invalidate_user_cache(tenant.slug, user.id)
    updated_user = svc.user_repository.get_by_id(user.id)
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    result = login_svc.issue_tokens_for_user(
        updated_user,
        ip=getattr(request.client, "host", None) if request.client else None,
        ua=request.headers.get("user-agent"),
        auto_login=True,
        tenant=tenant_auth_context(tenant),
    )
    return build_token_response(
        response=response,
        tenant=tenant,
        result=result,
        auto_login=True,
    )


@router.post("/auth/me/demo-unsubscribe", response_model=OperationStatusResponse)
@limiter.limit("5/minute")
def demo_unsubscribe(
    request: Request,
    tenant: RequiredTenantContextDep,
    user: User = Depends(get_current_user),
    signup_service: TenantSignupService = Depends(get_tenant_signup_service),
    body: DemoUnsubscribeRequest = Body(...),
):
    tenant_demo_mode = tenant_demo_mode_enabled(tenant)
    if not tenant_demo_mode:
        raise HTTPException(status_code=403, detail="Leiratkozás csak demo tenant esetén érhető el.")

    try:
        result = signup_service.request_demo_unsubscribe(
            tenant_slug=tenant.slug or "",
            email=(body.email or "").strip().lower(),
            requested_by_user_id=user.id,
            current_user_email=user.email,
        )
    except ValueError as exc:
        msg = str(exc)
        if msg == "email_required":
            raise HTTPException(status_code=400, detail="Az email cím megadása kötelező.")
        if msg == "email_mismatch":
            raise HTTPException(status_code=400, detail="A megerősítő email cím nem egyezik a bejelentkezett felhasználóéval.")
        raise HTTPException(status_code=400, detail=msg)

    tenant_slug = tenant.slug or ""
    allowlist_remove_by_user(tenant_slug, user.id)
    invalidate_user_cache(tenant_slug, user.id)
    return OperationStatusResponse(
        message="Leiratkozás rögzítve. 7 napon belül töröljük az összes tudástárat.",
        details={"deletion_due_days": result.get("deletion_due_days", 7)},
    )
