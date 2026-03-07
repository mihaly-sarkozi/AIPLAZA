# =============================================================================
# main.py – Alkalmazás belépési pont
# =============================================================================
# Mit csinál: Létrehozza a FastAPI appot, regisztrálja a middleware-eket (CORS,
# auth, rate limit kezelés, security headers) és az API routereket.
# Miért itt: Egy helyen látszik, milyen sorrendben futnak a dolgok és milyen
# végpontok érhetők el a /api alatt.
# =============================================================================
# Felgörgetve a program 3 fő részből áll:
#   1. Környezeti változók betöltése     – .env → konfig, titkok
#   2. Applikáció definiálása – FastApi
#   3. Védelem kialakítása, definiálása   – CORS, auth, rate limit, security headers
#   4. API végpontok beállítása           – routerek /api prefix alatt
# =============================================================================

"""
Segédmodulok importálása
"""

from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request
from slowapi.errors import RateLimitExceeded

from apps.core.i18n.messages import get_message, lang_from_request

from config.settings import settings
from apps.core.middleware.tenant_middleware import TenantMiddleware
from apps.core.middleware.auth_middleware import AuthMiddleware
from apps.core.middleware.csrf_middleware import CSRFMiddleware
from apps.core.middleware.correlation_id_middleware import CorrelationIdMiddleware
from apps.core.middleware.request_timing_middleware import RequestTimingMiddleware
from apps.core.di import get_token_service, get_login_service, get_tenant_repository
from apps.core.middleware.rate_limit_middleware import limiter
from apps.chat.presentation import chat_router
from apps.auth.presentation import auth_router
from apps.users.presentation import user_router
from apps.settings.presentation import settings_router
from apps.knowledge.presentation import knowledge_router

import logging
import os
import sys
# Lassú kérés / tenant / auth logok a konzolon (uvicorn stderr); force=True hogy uvicorn után is látszódjon
logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(name)s: %(message)s", stream=sys.stderr, force=True)


#   1. Környezet betöltése (.env)
# ======================================================================================================================================
# ======================================================================================================================================
# ======================================================================================================================================
"""
Futási paraméterek betöltése
Mit csinál: Betölti a futási paramétereket a .env fájlból.
"""
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)



#   2. Applikáció definiálása – FastApi
# ======================================================================================================================================
# ======================================================================================================================================
# ======================================================================================================================================

"""
Induláskor egy DB kapcsolatot nyitunk és bezárunk (pool warm-up), így az első
felhasználói kérés nem fizet az első TCP + auth késleltetéssel.
A debugger (debugpy) továbbra is lassíthat: éles sebességméréshez futtasd
uvicorn-t debug nélkül: python -m uvicorn main:app --host 127.0.0.1 --port 8001
"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from apps.core.container.app_container import container
        from apps.core.middleware.tenant_middleware import warm_tenant_cache
        with container.db_session_factory() as session:
            session.execute(text("SELECT 1"))
        # Tenant cache warm-up: első /me csak 1 DB hívást (user) fizet, nem 2-t (tenant+user)
        warm_tenant_cache("demo", container.tenant_repo)
    except Exception:
        pass  # pl. DB még nincs, seed_user/init_db kell
    yield
    # shutdown: security/audit event channel worker leállítása
    try:
        from apps.core.container.app_container import container
        if getattr(container, "event_channel", None) is not None:
            container.event_channel.stop()
    except Exception:
        pass
    # shutdown: központi Redis kapcsolat bezárása (allowlist, rate limit store)
    try:
        from apps.core.redis_client import close_redis
        close_redis()
    except Exception:
        pass


""" 
Alkalmazás példány
Mit csinál: Egy FastAPI alkalmazás objektum; ehhez kapcsoljuk a middleware-eket
és a routereket. A title a Swagger/OpenAPI docs-ban jelenik meg.
Miért: A FastAPI ezen az app-on keresztül kezeli az összes kérést és választ.
Swagger UI: http://127.0.0.1:8000/docs  – végpontok, try it out, sémák.
"""

app = FastAPI(
    title="BrainBankCenter.com",
    description="API dokumentáció – auth, users, settings, chat, knowledge base.",
    version="1.0",
    docs_url="/docs",   # Swagger UI
    redoc_url="/redoc", # ReDoc (alternatíva)
    lifespan=lifespan,
)




#   3. Védelem kialakítása, definiálása   – CORS, auth, rate limit, security headers
# ======================================================================================================================================
# ======================================================================================================================================
# ======================================================================================================================================

"""
CORS (Cross-Origin Resource Sharing)
- allow_origins: fix lista a configból (CORS_ORIGINS, vesszővel elválasztva).
- allow_origin_regex: minden subdomain a tenant_base_domain alatt (pl. *.local, *.teappod.hu)
  így több aldomain (demo.local, acme.local, …) automatikusan engedélyezett, nem kell egyenként felsorolni.
"""
import re

_cors_origins = [s.strip() for s in settings.cors_origins.split(",") if s.strip()]
_base = re.escape(settings.tenant_base_domain)
if settings.tenant_base_domain == "local":
    # Dev: *.local + localhost (bármely port)
    _cors_origin_regex = rf"^https?://(localhost|([a-z0-9][a-z0-9-]*\.)?{_base})(:\d+)?$"
else:
    # Prod: *.teappod.hu (és a bare domain) bármely port
    _cors_origin_regex = rf"^https?://([a-z0-9][a-z0-9-]*\.)?{_base}(:\d+)?$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=_cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)

"""
Auth middleware (a Tenant UTÁN kell regisztrálni, hogy a stackben a Tenant fusson előbb!)
Mit csinál: JWT ellenőrzés (user_token_payload), majd ha access token: User betöltése
DB-ből és request.state.user beállítása. A user_repository a current_tenant_schema
alapján használja a session search_path-ot – ezért a TenantMiddleware-nek előbb
kell futnia, különben "relation users does not exist" (public sémában nincs users).
"""
# Light path: csak ott nincs DB user fetch, ahol tényleg elég a token+allowlist+role (pl. /api/chat).
# Write/admin/settings/permission végpontok mindig full auth. docs/Auth_light_paths.md
_light_paths = tuple(p.strip() for p in (getattr(settings, "auth_light_paths", "") or "").split(",") if p.strip())
app.add_middleware(
    AuthMiddleware,
    token_service=get_token_service(),
    login_service=get_login_service(),
    light_paths=_light_paths,
)

"""
Tenant middleware (subdomain → tenant_id, current_tenant_schema)
Mit csinál: Host headerből kinyeri a slug-ot (pl. demo.local → demo), tenant
lekérdezése, request.state.tenant_id/tenant_slug és current_tenant_schema beállítása.
FONTOS: Ez futjon a kérésnél ELŐBB mint az Auth, hogy a DB session a megfelelő sémában keresse a users táblát.
"""
app.add_middleware(
    TenantMiddleware,
    tenant_repo=get_tenant_repository(),
    base_domain=settings.tenant_base_domain,
)

"""
Időmérés + X-Response-Time-Ms (ASGI middleware, alacsony overhead).
"""
app.add_middleware(RequestTimingMiddleware)

"""
Correlation/request ID (security log, audit, SIEM)
X-Request-ID header vagy generált UUID → request.state.correlation_id; válaszban X-Request-ID.
"""
app.add_middleware(CorrelationIdMiddleware)

"""
Rate limiting (slowapi)
Mit csinál: A limiter objektumot az app.state-ba teszi; az egyes route-ok
a @limiter.limit("X/minute") dekorátorral korlátozzák a kérésszámot. Ha valaki
túllépi, a slowapi RateLimitExceeded kivételt dob.
Miért: Így egy felhasználó vagy IP nem terheli le a szervert túl sok kéréssel;
a 429 válasz és a custom handler (lent) magyar üzenetet ad.
"""

app.state.limiter = limiter

"""
Mit csinál: Ha a slowapi RateLimitExceeded kivétel dobódik, ez a függvény
válaszol: 429 status és magyar "Túl sok kérés" üzenet.
Miért: A felhasználónak érthető visszajelzés kell, nem a slowapi alapértelmezett
angol szövege.
"""

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Túl sok kérés. Próbáld újra később."}
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Ha a detail dict és van 'code' kulcs, a 'message' a kérés nyelve alapján kerül be (i18n)."""
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        lang = lang_from_request(request)
        content = dict(exc.detail)
        content["message"] = get_message(content["code"], lang)
        return JSONResponse(status_code=exc.status_code, content={"detail": content})
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

"""
Security headers middleware (ASGI)
Minden kimenő HTTP válaszhoz biztonsági fejléceket ad: X-Frame-Options, X-Content-Type-Options, stb.
"""

# Teljes CSP: default-src, script-src, style-src, img-src, connect-src, frame-ancestors, object-src, base-uri.
# API backend: a válaszokra kerül; ha a backend szolgál HTML-t (pl. /docs), ezek korlátozzák a betöltéseket.
_CSP_DIRECTIVES = (
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",  # Swagger/Redoc inline style miatt
    "img-src 'self' data:",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'self'",
)
_CSP_HEADER_VALUE = "; ".join(_CSP_DIRECTIVES)


class SecurityHeadersMiddleware:
    """CSP és security headerek; teljes policy (default-src, script-src, connect-src, img-src, style-src, frame-ancestors, stb.)."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-frame-options", b"DENY"))
                headers.append((b"x-content-type-options", b"nosniff"))
                headers.append((b"x-xss-protection", b"1; mode=block"))
                headers.append((b"referrer-policy", b"strict-origin-when-cross-origin"))
                headers.append((b"content-security-policy", _CSP_HEADER_VALUE.encode("utf-8")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)

# CSRF: tesztekben DISABLE_CSRF=1 (conftest), így a TestClient nem kell token-t küldjön
if os.environ.get("DISABLE_CSRF") != "1":
    app.add_middleware(CSRFMiddleware)
app.add_middleware(SecurityHeadersMiddleware)




#   4. API végpontok beállítása           – routerek /api prefix alatt
# ======================================================================================================================================
# ======================================================================================================================================
# ======================================================================================================================================

"""
API routerek
Mit csinál: Minden router végpontjait a /api prefix alá regisztrálja. A tags
a Swagger UI-ban csoportosítja a végpontokat (chat, auth, users, stb.).
Miért: Egyértelmű, hogy minden „üzleti” API az /api alatt van; a frontend
erre az alap URL-re épít. A tag-ek segítenek a dokumentáció olvashatóságában.
"""

app.include_router(auth_router.router, prefix="/api", tags=["auth"])
app.include_router(chat_router.router, prefix="/api", tags=["chat"])
app.include_router(user_router.router, prefix="/api", tags=["users"])
app.include_router(settings_router.router, prefix="/api", tags=["settings"])
app.include_router(knowledge_router.router, prefix="/api", tags=["knowledge"])
