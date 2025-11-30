from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi.errors import RateLimitExceeded

from apps.core.middleware.auth_middleware import AuthMiddleware
from apps.core.di import get_token_service
from apps.chat.presentation import chat_router
from apps.auth.presentation import auth_router, user_router
from apps.knowledge.presentation import knowledge_router

from apps.core.middleware.rate_limit_middleware import limiter       # ha itt van

# --- 0️⃣ Alkalmazás létrehozása ---
app = FastAPI(title="BrainBankCenter.com")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

# --- Auth middleware ---
app.add_middleware(AuthMiddleware, token_service=get_token_service())

# --- Rate limiting ---
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Túl sok kérés. Próbáld újra később."}
    )

# --- Security headers ---
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
app.include_router(chat_router.router, prefix="/api", tags=["chat"])
app.include_router(auth_router.router, prefix="/api", tags=["auth"])
app.include_router(user_router.router, prefix="/api", tags=["users"])
app.include_router(knowledge_router.router, prefix="/api", tags=["knowledge"])
