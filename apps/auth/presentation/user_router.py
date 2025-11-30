# apps/auth/presentation/user_router.py
"""
User kezelési végpontok (csak superuser számára).
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from apps.core.middleware.rate_limit_middleware import limiter

from apps.core.di import get_user_service
from apps.auth.application.services.user_service import UserService
from apps.auth.adapter.http.request import UserCreateReq, UserUpdateReq
from apps.auth.adapter.http.response import UserOut
from apps.auth.domain.user import User
from apps.core.security.auth_dependencies import get_current_user

router = APIRouter()


def get_current_superuser(user: User = Depends(get_current_user)) -> User:
    """Csak superuser hozzáférhet."""
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser privileges required")
    return user


@router.get("/users", response_model=list[UserOut])
@limiter.limit("30/minute")
def list_users(
    request: Request,
    svc: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_superuser)
):
    """Összes user listázása (csak superuser)."""
    users = svc.list_all()
    return [
        UserOut(
            id=u.id,
            email=u.email,
            role=u.role,
            is_active=u.is_active,
            is_superuser=u.is_superuser,
            created_at=u.created_at
        )
        for u in users
    ]


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    svc: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_superuser)
):
    """User lekérése ID alapján (csak superuser)."""
    user = svc.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at
    )


@router.post("/users", response_model=UserOut)
@limiter.limit("10/minute")
def create_user(
    request: Request,
    data: UserCreateReq,
    svc: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_superuser)
):
    """Új user létrehozása (csak superuser)."""
    try:
        user = svc.create(
            email=data.email,
            password=data.password,
            role=data.role,
            is_superuser=data.is_superuser
        )
        return UserOut(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/users/{user_id}", response_model=UserOut)
@limiter.limit("20/minute")
def update_user(
    request: Request,
    user_id: int,
    data: UserUpdateReq,
    svc: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_superuser)
):
    """User frissítése (csak superuser, superuser nem módosítható)."""
    try:
        user = svc.update(
            user_id=user_id,
            email=data.email,
            role=data.role,
            is_active=data.is_active
        )
        return UserOut(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/users/{user_id}")
@limiter.limit("10/minute")
def delete_user(
    request: Request,
    user_id: int,
    svc: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_superuser)
):
    """User törlése (csak superuser, superuser nem törölhető)."""
    try:
        svc.delete(user_id)
        return {"status": "ok", "message": "User deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

