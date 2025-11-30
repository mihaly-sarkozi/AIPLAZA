# core/middleware/auth_middleware.py
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from apps.core.security.token_service import TokenService

# Ez a middleware minden kérésnél megpróbálja kiolvasni és hitelesíteni az Authorization Bearer
# JWT tokent, majd a dekódolt user-információt a request.state.user mezőben
# elérhetővé teszi az endpointok számára.
# OPTIONS kérések esetén teljesen kihagyja az authot.

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token_service: TokenService):
        super().__init__(app)
        self.token_service = token_service

    async def dispatch(self, request: Request, call_next):

        # OPTIONS -> skip
        if request.method == "OPTIONS":
            return await call_next(request)

        token = None
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

        if token:
            try:
                payload = self.token_service.verify(token)
                request.state.user_token_payload = payload
            except Exception:
                request.state.user_token_payload = None
        else:
            request.state.user_token_payload = None

        return await call_next(request)
