"""Admin user management routes.

Responsibility: HTTP endpoints for user CRUD (/users, /users/{id}).
Only admin-level operations; self-service profile routes live in profile_router.
"""

from core.extensions.tenant.context.request_tenant_context import RequestTenantContext
from fastapi import APIRouter, Body, Depends, HTTPException, Request

from core.capabilities.users.dto import User
from core.capabilities.users.presenters.user_presenter import user_to_response
from core.capabilities.users.router.requests.user_create_request import UserCreateRequest
from core.capabilities.users.router.requests.user_update_request import UserUpdateRequest
from core.capabilities.users.router.responses.user_response import UserResponse
from core.capabilities.users.service import UserService
from core.capabilities.users.dependencies import get_user_service
from core.di import get_service
from core.extensions.tenant.helpers.tenant_frontend_url_helper import tenant_frontend_base_url_from_request
from core.kernel.middleware.security import invalidate_user_cache
from core.kernel.http_dependencies import require_tenant_context
from core.kernel.security.rate_limit import limiter
from core.platform.auth.auth_dependencies import require_permission
from core.platform.auth.permissions_changed_store import set as permissions_changed_set
from core.platform.auth.token_allowlist import remove_by_user as allowlist_remove_by_user
from core.platform.service_keys import PLATFORM_TENANT_USAGE_SERVICE
from lang.messages import ErrorCode
from shared.presentation import LocalizedPresenterBase

router = APIRouter()
_presenter = LocalizedPresenterBase()



@router.get("/users", response_model=list[UserResponse])
@limiter.limit("30/minute")
def list_users(
    request: Request,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    svc: UserService = Depends(get_user_service),
    current_user: User = Depends(require_permission("users.read")),
):
    users = svc.list_all()
    result = []
    for user in users:
        if user.id is None or user.created_at is None:
            continue
        result.append(user_to_response(user))
    return result


@router.get("/users/{user_id}", response_model=UserResponse)
@limiter.limit("60/minute")
def get_user(
    request: Request,
    user_id: int,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    svc: UserService = Depends(get_user_service),
    current_user: User = Depends(require_permission("users.read")),
):
    user = svc.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.created_at is None:
        raise HTTPException(status_code=500, detail="User data is incomplete")
    return user_to_response(user)


@router.post("/users", response_model=UserResponse)
@limiter.limit("10/minute")
def create_user(
    request: Request,
    data: UserCreateRequest = Body(...),
    tenant: RequestTenantContext = Depends(require_tenant_context),
    svc: UserService = Depends(get_user_service),
    current_user: User = Depends(require_permission("users.write")),
):
    lang = _presenter.lang(request)
    try:
        usage_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
        allowed, reason = usage_service.can_create_user(tenant)
        if not allowed:
            raise HTTPException(status_code=400, detail=reason)
    except HTTPException:
        raise
    except Exception:
        pass  # usage service optional
    try:
        user = svc.create(
            email=data.email,
            name=data.name or None,
            role=data.role,
            request_base_url=tenant_frontend_base_url_from_request(request),
            created_by=current_user.id,
        )
        if user.created_at is None:
            raise HTTPException(status_code=500, detail="Failed to create user with timestamp")
        return user_to_response(user, pending_registration=True)
    except HTTPException:
        raise
    except ValueError as exc:
        message = str(exc)
        if "Email already exists" in message or "email already exists" in message.lower():
            raise HTTPException(status_code=400, detail=_presenter.detail_for_lang(ErrorCode.EMAIL_ALREADY_EXISTS, lang))
        raise HTTPException(status_code=400, detail={"code": "validation_error", "message": message})


@router.put("/users/{user_id}", response_model=UserResponse)
@limiter.limit("20/minute")
def update_user(
    request: Request,
    user_id: int,
    data: UserUpdateRequest = Body(...),
    tenant: RequestTenantContext = Depends(require_tenant_context),
    svc: UserService = Depends(get_user_service),
    current_user: User = Depends(require_permission("users.write")),
):
    try:
        user = svc.update(
            user_id=user_id,
            current_user_id=current_user.id or 0,
            name=data.name,
            is_active=data.is_active,
            email=data.email,
            role=data.role,
        )
        invalidate_user_cache(tenant.slug, user_id)
        if user.created_at is None:
            raise HTTPException(status_code=500, detail="User data is incomplete")
        if data.role is not None or data.is_active is not None:
            allowlist_remove_by_user(tenant.slug, user_id)
            permissions_changed_set(tenant.slug, user_id)
        return user_to_response(user)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/users/{user_id}")
@limiter.limit("10/minute")
def delete_user(
    request: Request,
    user_id: int,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    svc: UserService = Depends(get_user_service),
    current_user: User = Depends(require_permission("users.write")),
):
    try:
        allowlist_remove_by_user(tenant.slug, user_id)
        svc.delete(user_id, current_user_id=current_user.id or 0)
        return {"status": "ok", "message": "User deleted successfully"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
