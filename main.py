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
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from slowapi.errors import RateLimitExceeded

from apps.core.i18n.messages import get_message, lang_from_request

from config.settings import settings
from apps.core.middleware.tenant_middleware import TenantMiddleware
from apps.core.middleware.auth_middleware import AuthMiddleware
from apps.core.di import get_token_service, get_login_service, get_tenant_repository
from apps.core.middleware.rate_limit_middleware import limiter
from apps.chat.presentation import chat_router
from apps.auth.presentation import auth_router
from apps.users.presentation import user_router
from apps.settings.presentation import settings_router
from apps.knowledge.presentation import knowledge_router

import logging
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
    # shutdown: Redis allowlist kapcsolat bezárása
    try:
        from apps.core.security.token_allowlist import close_redis
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
    allow_headers=["Authorization", "Content-Type"],
)

"""
Auth middleware (a Tenant UTÁN kell regisztrálni, hogy a stackben a Tenant fusson előbb!)
Mit csinál: JWT ellenőrzés (user_token_payload), majd ha access token: User betöltése
DB-ből és request.state.user beállítása. A user_repository a current_tenant_schema
alapján használja a session search_path-ot – ezért a TenantMiddleware-nek előbb
kell futnia, különben "relation users does not exist" (public sémában nincs users).
"""
app.add_middleware(
    AuthMiddleware,
    token_service=get_token_service(),
    login_service=get_login_service(),
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
Részletes időmérés: kérés érkezés, middleware-k, válasz küldés – minden a terminálra.
"""
import logging
import time
from datetime import datetime, timezone
_request_log = logging.getLogger(__name__)

def _ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]

def _api_timing(msg: str):
    print(f"[TIME] {_ts()} {msg}", file=sys.stderr, flush=True)

class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = getattr(request.url, "path", "") or ""
        if not path.startswith("/api"):
            return await call_next(request)
        t0 = time.monotonic()
        _api_timing(f"REQUEST IN   {request.method} {path}")
        response = await call_next(request)
        elapsed = time.monotonic() - t0
        _api_timing(f"REQUEST OUT  {request.method} {path}  total={elapsed:.3f}s")
        # Postmanben látható: a backend ezt az idő alatt válaszolt (a ~4s DNS/kapcsolat előtte van)
        response.headers["X-Response-Time-Ms"] = str(int(elapsed * 1000))
        return response

app.add_middleware(RequestTimingMiddleware)

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
Security headers middleware
Mit csinál: Minden kimenő HTTP válaszhoz hozzáad biztonsági fejléceket:
  X-Frame-Options: DENY              – oldal ne kerülhessen iframe-be (clickjacking ellen)
  X-Content-Type-Options: nosniff    – böngésző ne találja ki a MIME típust
  X-XSS-Protection                    – régi XSS szűrő (támogatott böngészőkben)
  Referrer-Policy                     – referrer csak biztonságos átmenetekre
  Content-Security-Policy             – senki ne ágyazhassa iframe-be
Miért: Ezek a fejlécek csökkentik a clickjacking, MIME-sniffing és egyéb
alapvető webtámadások kockázatát; ajánlott minden éles szolgáltatásnál.
"""

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none';"
        return response

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
