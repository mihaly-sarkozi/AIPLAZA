from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

from apps.api.middleware.auth import AuthMiddleware
from infrastructure.security.tokens import TokenService
from apps.api.routers import chat, auth

# --- 0️⃣ Alkalmazás létrehozása ---
app = FastAPI(title="AIPLAZA")

# --- 1️⃣ CORS védelem ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://fixyourdoc.com",
        "https://www.fixyourdoc.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# --- 2️⃣ Auth middleware (JWT / PASETO token ellenőrzés) ---
token_service = TokenService(secret="supersecret", access_min=15, refresh_min=1440)
app.add_middleware(AuthMiddleware, token_service=token_service)

# --- 3️⃣ Rate limiting (DDoS, brute-force ellen) ---
from apps.api.middleware.rate_limit import limiter
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Túl sok kérés. Próbáld újra néhány másodperc múlva."},
    )

# --- 4️⃣ Biztonsági fejlécek middleware ---
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

# --- 5️⃣ Routerek ---
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
