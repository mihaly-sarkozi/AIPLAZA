# apps/auth/presentation/auth_router.py – Authentikáció (presentation réteg)
# Ez a fájl definiálja az authentikációs végpontokat.
# A végpont indulásnál ellenőrzi a paramétereket és meghívja a megfelelő service-t.
# 2026.02.14 - Sárközi Mihály

import os
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Body
from pydantic import BaseModel, Field, field_validator
from passlib.hash import bcrypt_sha256 as pwd_hasher
from config.settings import settings
from apps.core.middleware.rate_limit_middleware import limiter, refresh_token_key
from apps.core.rate_limit.auth_limits import check_login_step1_email, check_login_step2_pending_token

from apps.core.di import get_login_service, get_refresh_service, get_logout_service, get_audit_service, get_token_service, set_tenant_context_from_request, get_user_service
from apps.core.db.tenant_context import current_tenant_schema

from apps.auth.application.services.login_service import LoginService
from apps.auth.application.dto import LoginSuccess, LoginTwoFactorRequired
from apps.auth.application.services.logout_service import LogoutService
from apps.auth.application.services.refresh_service import RefreshService

from apps.auth.adapter.http.request import LoginReq
from apps.auth.application.dto import LoginInput
from apps.auth.application.exceptions import TwoFactorEmailError, TwoFactorTooManyAttemptsError
from apps.auth.adapter.http.response import TokenResp, UserInfo, TwoFactorRequiredResp

from apps.users.domain.user import User
from apps.core.security.auth_dependencies import get_current_user, get_current_user_optional
from apps.core.security.token_service import TokenService
from apps.core.di import get_user_repository
from apps.users.application.services.user_service import UserService
from apps.core.security.token_allowlist import add as allowlist_add, remove_by_user as allowlist_remove_by_user
from apps.core.security.cookie_policy import set_refresh_cookie, clear_refresh_cookie
from apps.audit.application.audit_service import AuditService
from apps.core.i18n.messages import get_message, ErrorCode

# --- Nyelv a kérésből (Accept-Language), alapértelmezett hu ---
def _lang_from_request(request: Request) -> str:
    accept = request.headers.get("Accept-Language") or ""
    # pl. "hu-HU,hu;q=0.9,en;q=0.8" -> első tag "hu"
    first = accept.split(",")[0].strip().lower()[:2]
    return first if first in ("hu", "en") else "hu"

def _detail(code: ErrorCode, lang: str):
    """Válasz detail: kód + üzenet (többnyelvű); a kliens a code alapján is fordíthat."""
    return {"code": code.value, "message": get_message(code, lang)}

# --- HTTP adapter (be/kimenet) ---
# LoginReq, TokenResp, UserInfo, TwoFactorRequiredResp: adapter/http réteg DTO-i,
# a kliens és az application réteg közötti szerződés (validáció, szerializáció).

# --- Router: auth use case-ek HTTP végpontjai ---
# A main.py: include_router(auth_router.router, prefix="/api", tags=["auth"]).
# set_tenant_context_from_request: a sync route thread-ben is meglegyen a tenant séma (context var).
router = APIRouter(dependencies=[Depends(set_tenant_context_from_request)])

# -------------------------------------------------
# LOGIN
# HTTP: POST /api/auth/login, body: LoginReq. Hívja: LoginService.login();
# válasz: TokenResp + refresh cookie, vagy TwoFactorRequiredResp ha 2FA kell.
# -------------------------------------------------

@router.post("/auth/login")
@limiter.limit(lambda: f"{settings.rate_limit_login_per_minute}/minute")  # IP alapú; plusz célzott: email 10/óra, pending_token 5/perc (auth_limits)
def login(
    req: LoginReq,
    request: Request,
    response: Response,
    svc: LoginService = Depends(get_login_service)
):

    lang = _lang_from_request(request)

    # Tenant = Host subdomain; ha nincs, a middleware már 404-et adott.
    tenant_slug = getattr(request.state, "tenant_slug", None)
    if not tenant_slug:
        raise HTTPException(status_code=400, detail=_detail(ErrorCode.TENANT_REQUIRED, lang))
    # Sync route thread pool szálban fut: a session factory-nek kell a séma (search_path)
    current_tenant_schema.set(tenant_slug)

    # Ha már van bejelentkezett user (Authorization Bearer), előbb ki kell lépni
    if getattr(request.state, "user", None) is not None:
        raise HTTPException(status_code=409, detail=_detail(ErrorCode.ALREADY_LOGGED_IN, lang))

    # Célzott rate limit: step2 = pending_token + 2FA kód → 5/perc/token; step1 = email → 10/óra/email (tenant dimenzióval)
    tenant_slug = getattr(request.state, "tenant_slug", None)
    if getattr(req, "pending_token", None) and getattr(req, "two_factor_code", None):
        if not check_login_step2_pending_token(req.pending_token, tenant_slug):
            raise HTTPException(status_code=429, detail=_detail(ErrorCode.AUTH_RATE_LIMIT, lang))
    elif getattr(req, "email", None):
        if not check_login_step1_email(req.email, tenant_slug):
            raise HTTPException(status_code=429, detail=_detail(ErrorCode.AUTH_RATE_LIMIT, lang))
    
    # Adapter req → application DTO; service csak LoginInput-ot kap.
    client_host = getattr(request.client, "host", None) if request.client else None
    inp = LoginInput(
        email=req.email,
        password=req.password,
        pending_token=req.pending_token,
        two_factor_code=req.two_factor_code,
        ip=client_host,
        ua=request.headers.get("user-agent"),
        auto_login=getattr(req, "auto_login", False),
        tenant_slug=tenant_slug,
        correlation_id=getattr(request.state, "correlation_id", None),
        tenant_security_version=getattr(request.state, "tenant_security_version", 0) or 0,
    )
    try:
        result = svc.login(inp)
    except TwoFactorEmailError as e:
        raise HTTPException(status_code=503, detail=_detail(e.error_code, lang))
    except TwoFactorTooManyAttemptsError:
        raise HTTPException(
            status_code=429,
            detail=_detail(ErrorCode.TWO_FACTOR_TOO_MANY_ATTEMPTS, lang),
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        detail = _detail(ErrorCode.LOGIN_ERROR, lang)
        # Dev: a válaszban is látszik a kivétel (pl. hiányzó oszlop → futtasd init_db.py)
        if os.environ.get("APP_ENV", "dev").lower() != "prod":
            detail = {**detail, "debug_message": str(e)}
        raise HTTPException(status_code=500, detail=detail)

    if result is None:
        raise HTTPException(status_code=401, detail=_detail(ErrorCode.INVALID_CREDENTIALS, lang))

    # Ha a login sikeres akkor =>
    
    # Ha a 2. lépés kell mert 2FA van, akkor a pending_token-t adunk vissza a válaszban.
    if isinstance(result, LoginTwoFactorRequired):
        return TwoFactorRequiredResp(pending_token=result.pending_token)

    # Ha vagy nincs 2FA vagy az is megtörtént akkor=>   

    # Sikeres belépés: refresh cookie (HttpOnly, Secure, SameSite; domain nincs = host-only).
    # auto_login → 30 nap; nincs auto_login → refresh_ttl_session_hours (pl. 24 óra), ne session cookie (az inaktivitás után eldobható).
    if getattr(req, "auto_login", False):
        cookie_max_age = int(settings.refresh_ttl_days * 24 * 3600)
    else:
        cookie_max_age = int(getattr(settings, "refresh_ttl_session_hours", 24) * 3600)
    set_refresh_cookie(
        response,
        result.refresh_token,
        secure=settings.cookie_secure,
        samesite=getattr(settings, "cookie_samesite", "lax"),
        max_age=cookie_max_age,
    )
    
    # Allowlist: csak ezzel a jti-val érvényes a token (törlés/logout után 401)
    tenant_slug = getattr(request.state, "tenant_slug", None)
    allowlist_add(tenant_slug, result.user.id, result.access_jti)

    # Visszatérünk a tokenekkel (access + refresh a body-ban is) és a felhasználó adataival.
    return TokenResp(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        user=UserInfo(
            id=result.user.id,
            email=result.user.email,
            role=result.user.role,
            name=getattr(result.user, "name", None),
        )
    )

# -------------------------------------------------
# FORGOT PASSWORD
# HTTP: POST /api/auth/forgot-password, body: { email }. Ha az email szerepel, set-password linket küldünk.
# Ha nincs ilyen user, nem hibázunk (ne lehessen kideríteni). Mindig 200.
# -------------------------------------------------

def _frontend_base_url_for_set_password(request: Request) -> str:
    """Set-password link alap URL: host a kérésből, opcionális frontend port."""
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    hostname = host.split(":")[0] if ":" in host else host
    port = getattr(settings, "frontend_set_password_port", None)
    if port is not None:
        return f"{scheme}://{hostname}:{port}"
    return f"{scheme}://{host}"


class ForgotPasswordBody(BaseModel):
    email: str = Field(..., min_length=1, max_length=100, description="Email cím")


@router.post("/auth/forgot-password")
@limiter.limit("10/minute")
def forgot_password(
    body: ForgotPasswordBody,
    request: Request,
    svc: UserService = Depends(get_user_service),
):
    tenant_slug = getattr(request.state, "tenant_slug", None)
    if tenant_slug:
        current_tenant_schema.set(tenant_slug)
    base_url = _frontend_base_url_for_set_password(request)
    svc.forgot_password(body.email.strip(), request_base_url=base_url)
    return {"ok": True}


# -------------------------------------------------
# REFRESH
# HTTP: POST /api/auth/refresh, cookie: refresh_token. Hívja: RefreshService.refresh();
# válasz: TokenResp, új refresh cookie.
# -------------------------------------------------

@router.post("/auth/refresh", response_model=TokenResp)
@limiter.limit("20/5minute", key_func=refresh_token_key)  # 20 kérés / 5 perc / session (refresh token)
def refresh_tokens(
    request: Request,
    response: Response,
    svc: RefreshService = Depends(get_refresh_service),
    login_svc: LoginService = Depends(get_login_service),
):
    """Refresh token cookie-ból vagy X-Refresh-Token headerből; új access + refresh párt ad."""
    lang = _lang_from_request(request)
    rt = request.cookies.get("refresh_token") or request.headers.get("X-Refresh-Token")
    if not rt:
        raise HTTPException(status_code=401, detail=_detail(ErrorCode.NO_REFRESH_TOKEN, lang))

    tenant_slug = getattr(request.state, "tenant_slug", None)
    if tenant_slug:
        current_tenant_schema.set(tenant_slug)
    correlation_id = getattr(request.state, "correlation_id", None)
    tenant_security_version = getattr(request.state, "tenant_security_version", 0) or 0
    result = svc.refresh(
        rt,
        getattr(request.client, "host", None),
        request.headers.get("user-agent"),
        tenant_slug=tenant_slug,
        correlation_id=correlation_id,
        tenant_security_version=tenant_security_version,
    )
    if not result:
        raise HTTPException(status_code=401, detail=_detail(ErrorCode.INVALID_OR_REVOKED_REFRESH, lang))
    if isinstance(result, tuple) and len(result) == 2 and result[0] is None:
        code = result[1]
        if code == "re_2fa_required":
            raise HTTPException(status_code=401, detail=_detail(ErrorCode.RE_2FA_REQUIRED, lang))
        raise HTTPException(status_code=401, detail=_detail(ErrorCode.PERMISSIONS_CHANGED, lang))

    access, new_refresh, access_jti = result

    # Allowlist: új access token jti regisztrálása
    payload = svc.tokens.verify(new_refresh)
    user_id = int(payload["sub"])
    allowlist_add(tenant_slug, user_id, access_jti)

    # Új refresh cookie (ugyanaz a policy: auto_login → napok, különben session_hours)
    if payload.get("al"):
        cookie_max_age = int(settings.refresh_ttl_days * 24 * 3600)
    else:
        cookie_max_age = int(getattr(settings, "refresh_ttl_session_hours", 24) * 3600)
    set_refresh_cookie(
        response,
        new_refresh,
        secure=settings.cookie_secure,
        samesite=getattr(settings, "cookie_samesite", "lax"),
        max_age=cookie_max_age,
    )

    # user lekérése az új refresh payloadból (user_id már fent kiszámolva)
    user = login_svc.user_repository.get_by_id(user_id)

    return TokenResp(
        access_token=access,
        refresh_token=new_refresh,
        user=UserInfo(
            id=user.id,
            email=user.email,
            role=user.role,
            name=getattr(user, "name", None),
        )
    )

# -------------------------------------------------
# LOGOUT
# HTTP: POST /api/auth/logout. Nincs kötelező Bearer: ha van user (érvényes token), abból vesszük az id-t;
# ha nincs (lejárt token), a refresh token cookie-ból dekódoljuk a user_id-t (lejárat figyelmen kívül).
# Csendes kiléptetés: mindig 200 + { "ok": true }, mindig kiküldjük a usert (cookie törlés, allowlist).
# Hibát csak a log/audit táblába írjuk.
# -------------------------------------------------

@router.post("/auth/logout")
@limiter.limit("30/minute")  # lazább, de monitorozott (audit)
def logout(
    request: Request,
    response: Response,
    user: User | None = Depends(get_current_user_optional),
    svc: LogoutService = Depends(get_logout_service),
    audit_service: AuditService = Depends(get_audit_service),
    token_service: TokenService = Depends(get_token_service),
):
    """Ha van user (érvényes Bearer), abból; ha nincs, refresh tokenból (lejárt is ok) vesszük a user_id-t. Mindig kiléptetünk."""
    rt = request.cookies.get("refresh_token") or request.headers.get("X-Refresh-Token")
    ip = getattr(request.client, "host", None) if request.client else None
    ua = request.headers.get("user-agent")

    user_id: int | None = user.id if user else None
    if user_id is None and rt:
        payload = token_service.decode_ignore_exp(rt)
        if payload and payload.get("typ") == "refresh" and payload.get("sub"):
            user_id = int(payload["sub"])

    tenant_slug = getattr(request.state, "tenant_slug", None)
    correlation_id = getattr(request.state, "correlation_id", None)
    try:
        if rt:
            svc.logout(rt, ip=ip, ua=ua, tenant_slug=tenant_slug, correlation_id=correlation_id)
    except Exception as e:
        try:
            audit_service.log(
                "logout_error",
                user_id=user_id,
                details={"error": str(e)},
                ip=ip,
                user_agent=ua,
            )
        except Exception:
            pass
    finally:
        if user_id is not None:
            allowlist_remove_by_user(tenant_slug, user_id)
        clear_refresh_cookie(response, secure=settings.cookie_secure, samesite=getattr(settings, "cookie_samesite", "lax"))

    return {"ok": True}

# -------------------------------------------------
# ME (current user) - Bejelentkezett user adatai + effektív locale/theme
# Válasz: { id, email, role, name, preferred_locale?, preferred_theme?, locale, theme }.
# locale/theme = user vagy owner alapértelmezés (hu, light).
# -------------------------------------------------

def _effective_locale_theme(user: User, owner: User | None) -> tuple[str, str]:
    loc = getattr(user, "preferred_locale", None) or (getattr(owner, "preferred_locale", None) if owner else None) or "hu"
    th = getattr(user, "preferred_theme", None) or (getattr(owner, "preferred_theme", None) if owner else None) or "light"
    return (loc if loc in ("hu", "en", "es") else "hu", th if th in ("light", "dark") else "light")


@router.get("/auth/me")
def me(
    user: User = Depends(get_current_user),
    user_repo=Depends(get_user_repository),
):
    owner = user_repo.get_owner()
    locale, theme = _effective_locale_theme(user, owner)
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "name": getattr(user, "name", None),
        "preferred_locale": getattr(user, "preferred_locale", None),
        "preferred_theme": getattr(user, "preferred_theme", None),
        "locale": locale,
        "theme": theme,
    }


class UpdateMeBody(BaseModel):
    name: str | None = Field(None, max_length=100, description="Felhasználó neve")
    preferred_locale: str | None = None
    preferred_theme: str | None = None


class ChangePasswordBody(BaseModel):
    current_password: str = Field(..., min_length=1, description="Jelenlegi jelszó")
    new_password: str = Field(..., min_length=6, description="Új jelszó (min. 6 karakter, kisbetű, nagybetű, szám)")

    @field_validator("new_password")
    @classmethod
    def new_password_strong(cls, v: str) -> str:
        from apps.users.adapter.http.request.set_password_req import validate_password_strength
        ok, msg = validate_password_strength(v)
        if not ok:
            raise ValueError(msg or "Invalid password")
        return v


# -------------------------------------------------
# POST /auth/me/change-password - Jelszó változtatás (régi ellenőrzés, majd mentés).
# -------------------------------------------------

@router.post("/auth/me/change-password")
@limiter.limit("10/minute")
def change_password(
    body: ChangePasswordBody,
    request: Request,
    user: User = Depends(get_current_user),
    user_repo=Depends(get_user_repository),
):
    """Jelenlegi jelszó ellenőrzése; ha helyes, új jelszó mentése. Hibás jelenlegi → 400."""
    lang = _lang_from_request(request)
    if not pwd_hasher.verify(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail=_detail(ErrorCode.CURRENT_PASSWORD_WRONG, lang))
    new_hash = pwd_hasher.hash(body.new_password)
    user_repo.update_password(user.id, new_hash)
    user_repo.reset_failed_login(user.id)
    return {"ok": True}


# -------------------------------------------------
# PATCH /auth/me - Profil: név, preferred_locale, preferred_theme (csak saját).
# -------------------------------------------------

@router.patch("/auth/me")
def update_me(
    body: UpdateMeBody = Body(default=UpdateMeBody()),
    user: User = Depends(get_current_user),
    user_repo=Depends(get_user_repository),
):
    name = body.name
    preferred_locale = body.preferred_locale
    preferred_theme = body.preferred_theme
    updates = {}
    if name is not None:
        updates["name"] = str(name).strip() or None
    if preferred_locale is not None:
        v = str(preferred_locale).strip().lower() if preferred_locale else None
        if v and v not in ("hu", "en", "es"):
            v = None
        updates["preferred_locale"] = v
    if preferred_theme is not None:
        v = str(preferred_theme).strip().lower() if preferred_theme else None
        if v and v not in ("light", "dark"):
            v = None
        updates["preferred_theme"] = v
    if not updates:
        owner = user_repo.get_owner()
        locale, theme = _effective_locale_theme(user, owner)
        return {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "name": getattr(user, "name", None),
            "preferred_locale": getattr(user, "preferred_locale", None),
            "preferred_theme": getattr(user, "preferred_theme", None),
            "locale": locale,
            "theme": theme,
        }
    updated = user.with_updates(**updates)
    result = user_repo.update(updated)
    owner = user_repo.get_owner()
    locale, theme = _effective_locale_theme(result, owner)
    return {
        "id": result.id,
        "email": result.email,
        "role": result.role,
        "name": getattr(result, "name", None),
        "preferred_locale": getattr(result, "preferred_locale", None),
        "preferred_theme": getattr(result, "preferred_theme", None),
        "locale": locale,
        "theme": theme,
    }


# -------------------------------------------------
# GET /auth/default-settings - Nyelv/téma a bejelentkezési oldalhoz (owner alapértelmezése).
# Auth nélkül, tenant a requestből (subdomain).
# -------------------------------------------------

@router.get("/auth/default-settings")
def default_settings(user_repo=Depends(get_user_repository)):
    owner = user_repo.get_owner()
    locale = (getattr(owner, "preferred_locale", None) or "hu") if owner else "hu"
    theme = (getattr(owner, "preferred_theme", None) or "light") if owner else "light"
    if locale not in ("hu", "en", "es"):
        locale = "hu"
    if theme not in ("light", "dark"):
        theme = "light"
    return {"locale": locale, "theme": theme}
