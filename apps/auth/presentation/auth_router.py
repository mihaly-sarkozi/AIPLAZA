# apps/auth/presentation/auth_router.py
"""
Authentikációs belépési pontok
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from apps.core.middleware.rate_limit_middleware import limiter

from apps.core.di import get_login_service, get_refresh_service, get_logout_service

from apps.auth.application.services.login_service import LoginService
from apps.auth.application.services.logout_service import LogoutService
from apps.auth.application.services.refresh_service import RefreshService

from apps.auth.adapter.http.request import LoginReq
from apps.auth.adapter.http.response import TokenResp, UserInfo

from apps.auth.domain.user import User
from apps.core.security.auth_dependencies import get_current_user

router = APIRouter()

# -------------------------------------------------
# LOGIN
# -------------------------------------------------

@router.post("/auth/login", response_model=TokenResp)
@limiter.limit("5/minute")
def login(
    req: LoginReq,
    request: Request,
    response: Response,
    svc: LoginService = Depends(get_login_service)
):
    access, refresh = svc.login(
        req.email,
        req.password,
        request.client.host,
        request.headers.get("user-agent")
    )

    if not access:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # refresh cookie beállítása
    response.set_cookie(
        "refresh_token",
        refresh,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/api",
    )

    # user lekérése
    user = svc.users.get_by_email(req.email)

    return TokenResp(
        access_token=access,
        user=UserInfo(
            id=user.id,
            email=user.email,
            role=user.role,
            is_superuser=user.is_superuser
        )
    )

# -------------------------------------------------
# REFRESH
# -------------------------------------------------

@router.post("/auth/refresh", response_model=TokenResp)
@limiter.limit("5/minute")
def refresh_tokens(
    request: Request,
    response: Response,
    svc: RefreshService = Depends(get_refresh_service)
):
    rt = request.cookies.get("refresh_token")
    if not rt:
        raise HTTPException(status_code=401, detail="No refresh cookie")

    result = svc.refresh(rt, request.client.host, request.headers.get("user-agent"))
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or revoked refresh")

    access, new_refresh = result

    # új refresh cookie
    response.set_cookie(
        "refresh_token",
        new_refresh,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/api",
    )

    # user lekérése az új refresh payloadból
    payload = svc.tokens.verify(new_refresh)
    user_id = int(payload["sub"])

    # user lekérése login service-ből
    login_svc = get_login_service()
    user = login_svc.users.get_by_id(user_id)

    return TokenResp(
        access_token=access,
        user=UserInfo(
            id=user.id,
            email=user.email,
            role=user.role,
            is_superuser=user.is_superuser
        )
    )

# -------------------------------------------------
# LOGOUT
# -------------------------------------------------

@router.post("/auth/logout")
@limiter.limit("10/minute")
def logout(
    request: Request,
    response: Response,
    svc: LogoutService = Depends(get_logout_service)
):
    rt = request.cookies.get("refresh_token")
    ok = False

    if rt:
        ok = svc.logout(rt)

    response.delete_cookie("refresh_token", path="/api")
    return {"ok": ok}

# -------------------------------------------------
# CURRENT USER
# -------------------------------------------------

@router.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_superuser": user.is_superuser
    }
