from fastapi import APIRouter, Depends, HTTPException, Request, Response
from apps.api.schemas.auth import LoginReq, TokenResp
from features.auth.application.services.login_service import LoginService
from features.auth.application.services.refresh_service import RefreshService
from features.auth.application.services.logout_service import LogoutService
from apps.api.di import get_login_service, get_refresh_service, get_logout_service

from apps.api.middleware.rate_limit import limiter

router = APIRouter()

@router.post("/auth/login", response_model=TokenResp)
@limiter.limit("5/minute")  # max 5 login próbálkozás / perc / IP
def login(req: LoginReq, request: Request, response: Response, svc: LoginService = Depends(get_login_service)):
    access, refresh = svc.login(req.email, req.password, request.client.host, request.headers.get("user-agent"))
    if not access:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # HttpOnly refresh cookie
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True, samesite="strict", path="/api")
    return TokenResp(access_token=access)

@router.post("/auth/refresh", response_model=TokenResp)
@limiter.limit("5/minute")  # max 5 refresh / perc / IP
def refresh(request: Request, response: Response, svc: RefreshService = Depends(get_refresh_service)):
    rt = request.cookies.get("refresh_token")
    if not rt:
        raise HTTPException(status_code=401, detail="No refresh cookie")

    result = svc.refresh(rt, request.client.host, request.headers.get("user-agent"))
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or revoked refresh")

    access, new_refresh = result

    # 🍪 új refresh token cookie
    response.set_cookie(
        "refresh_token", new_refresh,
        httponly=True, secure=True, samesite="strict", path="/api"
    )

    return TokenResp(access_token=access)
@router.post("/auth/logout")
@limiter.limit("10/minute")  # logout-ot kicsit lazábban engedjük
def logout(request: Request, response: Response, svc: LogoutService = Depends(get_logout_service)):
    rt = request.cookies.get("refresh_token")
    ok = False
    if rt: ok = svc.logout(rt)
    response.delete_cookie("refresh_token", path="/api/auth")
    return {"ok": ok}
