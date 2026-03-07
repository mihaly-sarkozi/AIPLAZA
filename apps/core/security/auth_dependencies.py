# core/security/auth_dependencies.py
# A usert a AuthMiddleware már betölti (request.state.user); itt ellenőrzünk (aktív-e) és visszaadjuk.
# 2026.03.07 - Sárközi Mihály

from fastapi import Depends, HTTPException, Request
from apps.users.domain.user import User
from apps.core.i18n.messages import get_message, lang_from_request, ErrorCode


def get_auth_light(request: Request) -> bool:
    """True, ha a middleware token-only (light) ágon autentikált; ilyenkor request.state.user minimál (id, role, is_active)."""
    return getattr(request.state, "auth_light", False)


def get_current_user(request: Request) -> User:
    """
    Bejelentkezett, aktív user a middleware-ből (request.state.user).
    Ha nincs user vagy inaktív (kitiltott) → 401. Minden védett végpontnál (chat, profil, jogosultságok, stb.) így ellenőrzünk.
    Light path-okon (pl. /api/chat, /api/knowledge) a user minimál (id, role, is_active); email/stb. üres.
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    if not getattr(user, "is_active", True):
        lang = lang_from_request(request)
        raise HTTPException(
            status_code=401,
            detail={"code": ErrorCode.PERMISSIONS_CHANGED.value, "message": get_message(ErrorCode.PERMISSIONS_CHANGED, lang)},
        )
    return user


def get_current_user_optional(request: Request) -> User | None:
    """
    User a middleware-ből, ha van érvényes token; különben None. Nem dob 401-et.
    Logout-nál: ha nincs érvényes Bearer, a refresh tokenból vesszük a user_id-t.
    """
    user = getattr(request.state, "user", None)
    if not user or not getattr(user, "is_active", True):
        return None
    return user


def get_current_user_id(request: Request) -> int:
    """
    Bejelentkezett user id – request.state.user-t a middleware tölti, itt csak .id.
    """
    return get_current_user(request).id


def get_current_user_admin(
    user: User = Depends(get_current_user)
):
    """
    Admin vagy owner szerepkör kell (beállítások, train, stb.).
    """
    if user.role not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Admin privileges required")

    return user
