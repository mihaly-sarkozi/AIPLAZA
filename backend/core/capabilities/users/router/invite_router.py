# Meghívásos regisztrációs végpontok.
# 2026.04.03 - Sárközi Mihály

from fastapi import APIRouter, Depends, HTTPException, Request

from core.capabilities.users.dependencies import get_invite_service, get_user_service
from core.di import RequiredTenantContextDep
from core.kernel.security.rate_limit import limiter
from core.platform.auth.auth_dependencies import require_permission
from core.extensions.tenant.helpers.tenant_frontend_url_helper import tenant_frontend_base_url_from_request
from core.capabilities.users.dto import User
from core.capabilities.users.presenters.user_presenter import user_to_response
from core.capabilities.users.router.requests import SetPasswordRequest
from core.capabilities.users.router.responses import UserResponse
from core.capabilities.users.service import InviteService, UserService
from core.capabilities.users.service.invite_errors import InviteTokenExpiredError, InviteTokenInvalidError

router = APIRouter()

# Meghívó token érvényességének ellenőrzése
@router.get("/users/set-password/validate")
@limiter.limit("30/minute")
def validate_set_password_token(
    request: Request,
    tenant: RequiredTenantContextDep,
    token: str = "",
    invite_svc: InviteService = Depends(get_invite_service),
):
    status = invite_svc.validate_invite_token(token or "")
    if status == "valid":
        return {"valid": True}
    if status == "expired":
        raise HTTPException(
            status_code=410,
            detail={
                "valid": False,
                "reason": "expired",
                "message": "A regisztrációs link lejárt. Kérj újat az adminisztrátortól vagy ellenőrizd az email címed.",
            },
        )
    raise HTTPException(
        status_code=400,
        detail={
            "valid": False,
            "reason": "invalid",
            "message": "Az előző link már nem érvényes. Új linket küldtünk az email címedre – használd a legújabb emailben lévő linket. Ha nincs új link, kérj egyet az adminisztrátortól.",
        },
    )

# Jelszó beállítás
@router.post("/users/set-password")
@limiter.limit("10/minute")
def set_password(
    request: Request,
    data: SetPasswordRequest,
    tenant: RequiredTenantContextDep,
    invite_svc: InviteService = Depends(get_invite_service),
):
    try:
        invite_svc.set_password(token=data.token, password=data.password)
        return {"message": "Jelszó beállítva. Most már be tudsz lépni."}
    except InviteTokenExpiredError:
        raise HTTPException(
            status_code=410,
            detail={
                "reason": "expired",
                "message": "A regisztrációs link lejárt. Kérj újat az adminisztrátortól vagy ellenőrizd az email címed.",
            },
        )
    except InviteTokenInvalidError:
        raise HTTPException(
            status_code=400,
            detail={
                "reason": "invalid",
                "message": "Az előző link már nem érvényes. Új linket küldtünk az email címedre – használd a legújabb emailben lévő linket. Ha nincs új link, kérj egyet az adminisztrátortól.",
            },
        )

# Meghívó újraküldése
@router.post("/users/{user_id}/resend-invite", response_model=UserResponse)
@limiter.limit("10/minute")
def resend_invite(
    request: Request,
    user_id: int,
    tenant: RequiredTenantContextDep,
    svc: UserService = Depends(get_user_service),
    invite_svc: InviteService = Depends(get_invite_service),
    current_user: User = Depends(require_permission("users.invite")),
):
    try:
        invite_svc.resend_invite(
            user_id,
            request_base_url=tenant_frontend_base_url_from_request(request),
            updated_by=current_user.id,
        )
        user = svc.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user_to_response(user, pending_registration=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
