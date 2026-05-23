# backend/core/modules/tenant/tokens/demo_jwt.py
# Feladat: Demo login JWT token service implementáció. Tenant slug, user email és lejárat alapján rövid életű demo login tokent állít elő és validál. Tenant onboarding token service.
# Sárközi Mihály - 2026.05.21

"""Demo login token service.

Responsibility: create, validate and decode signed demo-login JWT tokens,
and build the demo-login redirect URL.  No business orchestration – just
token I/O and URL construction.
"""
from __future__ import annotations

from typing import Any

import jwt


class DemoLoginTokenService:
    def __init__(
        self,
        *,
        token_service,
        request_base_url_builder,
        frontend_base_url: str,
        cookie_secure: bool,
        install_host: str,
        frontend_set_password_port: int | None,
    ) -> None:
        self._token_service = token_service
        self._request_base_url_builder = request_base_url_builder
        self._frontend_base_url = frontend_base_url
        self._cookie_secure = cookie_secure
        self._install_host = install_host
        self._frontend_set_password_port = frontend_set_password_port

    def _frontend_base_for_install_host(self) -> str:
        configured = (self._frontend_base_url or "").strip()
        if configured:
            return configured.rstrip("/")
        scheme = "https" if self._cookie_secure else "http"
        base = f"{scheme}://{self._install_host}"
        if self._frontend_set_password_port is not None:
            base = f"{base}:{self._frontend_set_password_port}"
        return base

    def build_demo_login_link(self, token: str, tenant_slug: str | None = None) -> str:
        if tenant_slug:
            tenant_base = self._request_base_url_builder(tenant_slug).rstrip("/")
            return f"{tenant_base}/demo-login?token={token}"
        return f"{self._frontend_base_for_install_host()}/demo-login?token={token}"

    def decode_demo_token(self, token: str) -> dict[str, Any]:
        try:
            claims = self._token_service.verify(token)
        except jwt.ExpiredSignatureError as exc:
            raise ValueError("demo_token_expired") from exc
        except jwt.InvalidTokenError as exc:
            raise ValueError("invalid_demo_token") from exc
        if claims.get("typ") != "demo_login":
            raise ValueError("invalid_demo_token")
        return claims

    def make_demo_login_token(
        self,
        *,
        user_id: int,
        tenant_slug: str,
        email: str,
        name: str | None,
        demo_expires_at,
    ) -> str:
        return self._token_service.make_demo_login(
            user_id=user_id,
            tenant_slug=tenant_slug,
            email=email,
            name=name,
            demo_expires_at=demo_expires_at,
        )

    def resolve_demo_login_redirect(self, token: str) -> str:
        claims = self.decode_demo_token(token)
        tenant_slug = str(claims.get("tenant") or "").strip().lower()
        if not tenant_slug:
            raise ValueError("invalid_demo_token")
        return self.build_demo_login_link(token, tenant_slug)


__all__ = ["DemoLoginTokenService"]
