# core/security/auth_dependencies.py
from fastapi import Depends, HTTPException, Request
from apps.core.di import get_login_service
from apps.auth.domain.user import User


def get_current_user_id(request: Request) -> int:
    """
    A JWT payload már a middleware-ben beolvasásra került.
    Itt csak döntést hozunk:
    - van-e payload?
    - jó-e a token típusa?
    - kiolvassuk-e a user ID-t?
    """
    payload = getattr(request.state, "user_token_payload", None)

    if not payload:
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    if payload.get("typ") != "access":
        raise HTTPException(status_code=401, detail="Wrong token type")

    # A JWT 'sub' mezőben van a user ID
    return int(payload["sub"])


def get_current_user(
    user_id: int = Depends(get_current_user_id),
    login_service = Depends(get_login_service)
) -> User:
    """
    Az authentikáció után betöltjük az aktuális user-t
    az application réteg LoginService-jével.
    """
    user = login_service.users.get_by_id(user_id)

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def get_current_user_admin(
    user: User = Depends(get_current_user)
):
    """
    Csak admin szerepkör engedélyezett.
    """
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")

    return user
