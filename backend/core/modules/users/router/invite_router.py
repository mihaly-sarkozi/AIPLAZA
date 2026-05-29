# backend/core/modules/users/router/invite_router.py
# Feladat: A meghívó és jelszóbeállítás HTTP adaptere. Invite token ellenőrzést, set password flow-t és kapcsolódó response mappinget köt UserService/InviteService műveletekhez. Users onboarding router réteg.
# Sárközi Mihály - 2026.05.21

from fastapi import APIRouter, Depends, HTTPException, Request

from core.kernel.http.responses import OperationStatusResponse
from core.modules.users.dependencies import get_invite_service, get_user_service
from core.kernel.http.tenant_dependencies import RequiredTenantContextDep
from core.kernel.security.rate_limit import limiter
from core.modules.auth.web.dependencies.auth_dependencies import require_permission
from core.modules.tenant.helpers.tenant_frontend_url_helper import tenant_frontend_base_url_from_request
from core.modules.users.domain.dto import User
from core.modules.users.web.presenters.user_presenter import user_to_response
from core.modules.users.router.requests import SetPasswordRequest
from core.modules.users.router.responses import UserResponse
from core.modules.users.service import InviteService, UserService
from core.modules.users.service.invite_errors import InviteTokenExpiredError, InviteTokenInvalidError

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
@router.post("/users/set-password", response_model=OperationStatusResponse)
@limiter.limit("10/minute")
def set_password(
    request: Request,
    data: SetPasswordRequest,
    tenant: RequiredTenantContextDep,
    invite_svc: InviteService = Depends(get_invite_service),
):
    try:
        invite_svc.set_password(token=data.token, password=data.password)
        return OperationStatusResponse(message="Jelszó beállítva. Most már be tudsz lépni.")
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
            invite_lang=getattr(current_user, "preferred_locale", None),
        )
        user = svc.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user_to_response(user, pending_registration=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
