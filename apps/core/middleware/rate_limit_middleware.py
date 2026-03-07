# apps/core/middleware/rate_limit_middleware.py 
# MIDDLEWARE - Rate limit kulcs és limiter
# Mit csinál: Egy slowapi Limiter példányt ad, ami a kérésszámot korlátozza.
# Csak annyi hívást engedélyez amennyit beállítunk minden fügvénynél, 
# Így nem lehet korlátlanul egy robottal lekérni sok adatot például vagy sokszor próbálkozni egy belépésnél. 
# A kulcs: bejelentkezett user esetén user_id (user_token_payload.sub), különben IP.
# A tényleges limitet az egyes route-ok állítják: @limiter.limit("X/minute").
# A limiter-t a main.py app.state.limiter-ként regisztrálja; a 429-et ott kezeli.
# 2026.02.14 - Sárközi Mihály

from slowapi import Limiter
from slowapi.util import get_remote_address


def user_or_ip_key(request):
    """
    Rate limit kulcs: bejelentkezett user → "user:{id}", egyébként "ip:{addr}".
    Az AuthMiddleware request.state.user_token_payload-ot tölti; a "sub" a user id.
    """
    payload = getattr(request.state, "user_token_payload", None)
    if payload and payload.get("sub"):
        return f"user:{payload['sub']}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=user_or_ip_key)


def refresh_token_key(request):
    """
    Rate limit kulcs refresh végponthoz: session (cookie/header refresh token) vagy IP.
    Így a limit 20/5perc per session lesz, nem globális IP.
    """
    rt = request.cookies.get("refresh_token") or request.headers.get("X-Refresh-Token")
    if rt:
        return f"refresh:{rt}"
    return f"ip:{get_remote_address(request)}"