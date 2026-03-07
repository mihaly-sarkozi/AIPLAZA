# apps/users/presentation/user_router.py
# User kezelési végpontok (csak superuser). Létrehozáskor nincs jelszó: emailben megy a link.
# 2026.02.28 - Sárközi Mihály

from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException, Request

from apps.core.middleware.rate_limit_middleware import limiter
from apps.core.di import get_user_service, get_session_repository, set_tenant_context_from_request
from apps.core.security.auth_dependencies import get_current_user
from apps.core.security.token_allowlist import remove_by_user as allowlist_remove_by_user
from apps.core.security.permissions_changed_store import set as permissions_changed_set
from apps.core.middleware.auth_middleware import invalidate_user_cache
from apps.core.i18n.messages import get_message, ErrorCode, lang_from_request
from apps.users.domain.user import User
from apps.users.application.services.user_service import UserService
from apps.users.adapter.http.request import UserCreateReq, UserUpdateReq, SetPasswordReq
from apps.users.adapter.http.response import UserOut

router = APIRouter(dependencies=[Depends(set_tenant_context_from_request)])


def _detail(code: ErrorCode, lang: str):
    """Válasz detail: kód + üzenet (többnyelvű); a kliens a code alapján is fordíthat."""
    return {"code": code.value, "message": get_message(code, lang)}


def _request_base_url(request: Request) -> str:
    """Scheme + host a kérésből (proxy: X-Forwarded-Proto, X-Forwarded-Host)."""
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{scheme}://{host}"


def _frontend_base_url_for_set_password(request: Request) -> str:
    """A set-password link alap URL-je: host a kérésből, port a frontend port (ha megadva), különben a kérés portja."""
    from config.settings import settings
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    hostname = host.split(":")[0] if ":" in host else host
    port = getattr(settings, "frontend_set_password_port", None)
    if port is not None:
        return f"{scheme}://{hostname}:{port}"
    return f"{scheme}://{host}"

# Tenant ID lekérése a request.state.tenant_id alapján, ami a host alapján van beállítva a TenantMiddleware-ben.
def get_tenant_id(request: Request) -> int:
    tid = getattr(request.state, "tenant_id", None)
    if not tid:
        raise HTTPException(
            status_code=400,
            detail="Tenant hiányzik. Használd a céges aldomaint (pl. acme.localhost)."
        )
    return tid

# Admin vagy owner vihet fel/szerkeszthet/törölhet usert (owner nem törölhető); a user listázás is csak nekik.
def get_current_admin_or_owner(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("admin", "owner"):
        raise HTTPException(
            status_code=403,
            detail="Csak admin vagy owner vihet fel, szerkeszthet vagy törölhet felhasználót."
        )
    return user

# Összes user listázása
@router.get("/users", response_model=list[UserOut])
@limiter.limit("30/minute")
def list_users(
    request: Request,
    _tenant_id: int = Depends(get_tenant_id),
    svc: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_admin_or_owner)
):
    users = svc.list_all()
    result = []
    for u in users:
        if u.id is None or u.created_at is None:
            continue
        user_dict = asdict(u)
        user_dict.pop('password_hash', None)
        user_dict.pop("registration_completed_at", None)
        user_dict["pending_registration"] = not u.is_active and (getattr(u, "registration_completed_at", None) is None)
        result.append(UserOut.model_validate(user_dict))
    return result

# Egy user adatainak lekérése
@router.get("/users/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    svc: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_admin_or_owner)
):
    user = svc.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.created_at is None:
        raise HTTPException(status_code=500, detail="User data is incomplete")
    user_dict = asdict(user)
    user_dict.pop('password_hash', None)
    user_dict.pop("registration_completed_at", None)
    user_dict["pending_registration"] = not user.is_active and (getattr(user, "registration_completed_at", None) is None) if user.id else False
    return UserOut.model_validate(user_dict)

# Új user létrehozása (jelszó nélkül; a user emailben kap linket, 24h alatt beállítja a jelszót)
@router.post("/users", response_model=UserOut)
@limiter.limit("10/minute")
def create_user(
    request: Request,
    data: UserCreateReq,
    _tenant_id: int = Depends(get_tenant_id),
    svc: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_admin_or_owner)
):
    lang = lang_from_request(request)
    try:
        user = svc.create(
            email=data.email,
            name=data.name or None,
            role=data.role,
            request_base_url=_frontend_base_url_for_set_password(request),
        )
        if user.created_at is None:
            raise HTTPException(status_code=500, detail="Failed to create user with timestamp")
        user_dict = asdict(user)
        user_dict.pop('password_hash', None)
        user_dict.pop("registration_completed_at", None)
        user_dict["pending_registration"] = True
        return UserOut.model_validate(user_dict)
    except ValueError as e:
        msg = str(e)
        if "Email already exists" in msg or "email already exists" in msg.lower():
            raise HTTPException(status_code=400, detail=_detail(ErrorCode.EMAIL_ALREADY_EXISTS, lang))
        raise HTTPException(status_code=400, detail={"code": "validation_error", "message": msg})


# Regisztrációs/set-password link érvényesség ellenőrzése – auth NINCS (a link token a hitelesítés)
@router.get("/users/set-password/validate")
@limiter.limit("30/minute")
def validate_set_password_token(
    request: Request,
    token: str = "",
    _tenant_id: int = Depends(get_tenant_id),
    svc: UserService = Depends(get_user_service),
):
    status = svc.validate_invite_token(token or "")
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


# Jelszó beállítás a meghívott usernek (token + jelszó) – auth NINCS (a link token a hitelesítés)
@router.post("/users/set-password")
@limiter.limit("10/minute")
def set_password(
    request: Request,
    data: SetPasswordReq,
    _tenant_id: int = Depends(get_tenant_id),
    svc: UserService = Depends(get_user_service),
):
    try:
        svc.set_password(token=data.token, password=data.password)
        return {"message": "Jelszó beállítva. Most már be tudsz lépni."}
    except ValueError as e:
        msg = str(e)
        if msg == "token_expired":
            raise HTTPException(
                status_code=410,
                detail={
                    "reason": "expired",
                    "message": "A regisztrációs link lejárt. Kérj újat az adminisztrátortól vagy ellenőrizd az email címed.",
                },
            )
        if msg == "invalid_token":
            raise HTTPException(
                status_code=400,
                detail={
                    "reason": "invalid",
                    "message": "Az előző link már nem érvényes. Új linket küldtünk az email címedre – használd a legújabb emailben lévő linket. Ha nincs új link, kérj egyet az adminisztrátortól.",
                },
            )
        raise HTTPException(status_code=400, detail={"message": msg})

# Egy user adatainak frissítése
@router.put("/users/{user_id}", response_model=UserOut)
@limiter.limit("20/minute")
def update_user(
    request: Request,
    user_id: int,
    data: UserUpdateReq,
    _tenant_id: int = Depends(get_tenant_id),
    svc: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_admin_or_owner),
    session_repo=Depends(get_session_repository),
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
        if user.created_at is None:
            raise HTTPException(status_code=500, detail="User data is incomplete")
        # Role vagy is_active változott → token, session, security_version és auth cache érvénytelenítés; user újra be kell lépjen
        if data.role is not None or data.is_active is not None:
            tenant_slug = getattr(request.state, "tenant_slug", None)
            allowlist_remove_by_user(tenant_slug, user_id)
            session_repo.invalidate_all_for_user(user_id)
            permissions_changed_set(tenant_slug, user_id)
            invalidate_user_cache(tenant_slug, user_id)
            svc.increment_security_version(user_id)
        user_dict = asdict(user)
        user_dict.pop('password_hash', None)
        user_dict.pop("registration_completed_at", None)
        user_dict["pending_registration"] = not user.is_active and (getattr(user, "registration_completed_at", None) is None) if user.id else False
        return UserOut.model_validate(user_dict)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Regisztrációs link újraküldése (csak regisztráció alatti usernek; a korábbi link érvénytelen lesz)
@router.post("/users/{user_id}/resend-invite", response_model=UserOut)
@limiter.limit("10/minute")
def resend_invite(
    request: Request,
    user_id: int,
    _tenant_id: int = Depends(get_tenant_id),
    svc: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_admin_or_owner)
):
    try:
        svc.resend_invite(user_id, request_base_url=_frontend_base_url_for_set_password(request))
        user = svc.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user_dict = asdict(user)
        user_dict.pop("password_hash", None)
        user_dict.pop("registration_completed_at", None)
        user_dict["pending_registration"] = True
        return UserOut.model_validate(user_dict)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Egy user törlése (aktív is törölhető; admin csak akkor, ha nem saját magát törli)
@router.delete("/users/{user_id}")
@limiter.limit("10/minute")
def delete_user(
    request: Request,
    user_id: int,
    svc: UserService = Depends(get_user_service),
    session_repo=Depends(get_session_repository),
    current_user: User = Depends(get_current_admin_or_owner)
):
    try:
        tenant_slug = getattr(request.state, "tenant_slug", None)
        session_repo.invalidate_all_for_user(user_id)
        allowlist_remove_by_user(tenant_slug, user_id)
        svc.delete(user_id, current_user_id=current_user.id or 0)
        return {"status": "ok", "message": "User deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
