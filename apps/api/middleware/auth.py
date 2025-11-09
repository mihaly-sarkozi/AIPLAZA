# apps/api/middleware/auth.py
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from infrastructure.security.tokens import TokenService

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token_service: TokenService):
        super().__init__(app)
        self.token_service = token_service

    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("Authorization")
        user = None

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            try:
                payload = self.token_service.verify(token)
                if payload.get("typ") == "access":
                    # csak érvényes access tokeneknél
                    user = type("UserCtx", (), payload)()
            except Exception:
                pass  # érvénytelen tokennél user marad None

        # elérhető lesz limiter és endpointok számára
        request.state.user = user

        return await call_next(request)
