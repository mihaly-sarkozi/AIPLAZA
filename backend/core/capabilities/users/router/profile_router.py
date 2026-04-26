"""Profile and self-service routes.

Responsibility: HTTP endpoints for the currently authenticated user
(/auth/me, change-password, set-initial-password, demo-unsubscribe).
No admin / user-management logic here.
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response

from core.capabilities.auth.router.auth_response_builder import build_token_response, tenant_auth_context
from core.capabilities.auth.router.responses.token_response import TokenResponse
from core.capabilities.auth.service.login_service import LoginService
from core.capabilities.users.dependencies import get_user_profile_service, get_user_service
from core.capabilities.users.dto import User
from core.capabilities.users.policies.profile_policy import tenant_demo_mode_enabled
from core.capabilities.users.router.requests.change_password_request import ChangePasswordRequest
from core.capabilities.users.router.requests.demo_unsubscribe_request import DemoUnsubscribeRequest
from core.capabilities.users.router.requests.forgot_password_request import ForgotPasswordRequest
from core.capabilities.users.router.requests.set_initial_password_request import SetInitialPasswordRequest
from core.capabilities.users.router.requests.update_me_request import UpdateMeRequest
from core.capabilities.users.service import UserService
from core.capabilities.users.service.profile_service import UserProfileService
from core.di import RequiredTenantContextDep, get_login_service, get_service
from core.extensions.tenant.dependencies import get_tenant_signup_service
from core.extensions.tenant.helpers.tenant_frontend_url_helper import tenant_frontend_base_url_from_request
from core.extensions.tenant.service import TenantSignupService
from core.kernel.middleware.security import invalidate_user_cache
from core.kernel.security.rate_limit import limiter
from core.platform.auth.auth_dependencies import get_current_user
from core.platform.auth.token_allowlist import remove_by_user as allowlist_remove_by_user
from core.platform.service_keys import PLATFORM_TENANT_USAGE_SERVICE
from lang.messages import ErrorCode
from shared.presentation import LocalizedPresenterBase

router = APIRouter()
_presenter = LocalizedPresenterBase()


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
    tenant: RequiredTenantContextDep,
    profile_service: UserProfileService = Depends(get_user_profile_service),
):
    return profile_service.get_default_settings()


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


@router.post("/auth/forgot-password")
@limiter.limit("10/minute")
def forgot_password(
    request: Request,
    tenant: RequiredTenantContextDep,
    svc: UserService = Depends(get_user_service),
    body: ForgotPasswordRequest = Body(...),
):
    base_url = tenant_frontend_base_url_from_request(request)
    svc.forgot_password(body.email.strip(), request_base_url=base_url)
    return {"ok": True}


@router.post("/auth/me/change-password")
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
    return {"ok": True}


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


@router.post("/auth/me/demo-unsubscribe")
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
    return {
        "ok": True,
        "deletion_due_days": result.get("deletion_due_days", 7),
        "message": "Leiratkozás rögzítve. 7 napon belül töröljük az összes tudástárat.",
    }
