"""Demo-login endpoint logic.

Responsibility: validate the one-time demo JWT, look up the user, and issue
tokens.  No cookie or allowlist management – that is delegated to
``build_token_response`` in auth_response_builder.
"""
from __future__ import annotations

from datetime import datetime, timezone

import jwt
from fastapi import HTTPException, Request, Response

from core.capabilities.auth.router.auth_response_builder import build_token_response, tenant_auth_context
from core.capabilities.auth.router.responses import TokenResponse
from core.capabilities.auth.service import LoginService
from core.kernel.clock import utc_now
from core.platform.auth.token_service import TokenService


def handle_demo_login(
    *,
    request: Request,
    response: Response,
    tenant,
    token: str,
    svc: LoginService,
    token_service: TokenService,
) -> TokenResponse:
    """Validate demo JWT and issue regular session tokens.

    Raises HTTPException on any validation failure.
    """
    try:
        claims = token_service.verify(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=410, detail={"reason": "expired", "message": "A demo link lejárt."})
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail={"reason": "invalid", "message": "A demo link érvénytelen."})

    if claims.get("typ") != "demo_login":
        raise HTTPException(status_code=400, detail={"reason": "invalid", "message": "A demo link érvénytelen."})
    if str(claims.get("tenant") or "").strip().lower() != (tenant.slug or "").strip().lower():
        raise HTTPException(
            status_code=400,
            detail={"reason": "invalid", "message": "A demo link nem ehhez a tenanthez tartozik."},
        )

    demo_expires_at = claims.get("demo_expires_at")
    if isinstance(demo_expires_at, (int, float)):
        demo_expires_dt = datetime.fromtimestamp(demo_expires_at, tz=timezone.utc)
        if demo_expires_dt <= utc_now():
            raise HTTPException(status_code=410, detail={"reason": "expired", "message": "A demo link lejárt."})

    user_id = int(claims.get("sub") or 0)
    user = svc.user_repository.get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail={"reason": "invalid", "message": "A demo felhasználó nem érhető el."})
    if user.email.strip().lower() != str(claims.get("email") or "").strip().lower():
        raise HTTPException(
            status_code=401,
            detail={"reason": "invalid", "message": "A demo linkhez tartozó felhasználó nem egyezik."},
        )
    result = svc.issue_tokens_for_user(
        user,
        ip=getattr(request.client, "host", None) if request.client else None,
        ua=request.headers.get("user-agent"),
        auto_login=True,
        tenant=tenant_auth_context(tenant),
    )
    return build_token_response(
        response=response,
        tenant=tenant,
        result=result,
        auto_login=True,
    )
