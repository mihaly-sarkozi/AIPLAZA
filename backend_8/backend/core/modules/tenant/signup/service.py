# backend/core/modules/tenant/signup/service.py
# Feladat: A tenant signup service façade. A router számára egyszerű belépési pontot ad a signup orchestrator műveleteihez, miközben a részletes onboarding logika a canonical signup use case-ekben marad. Tenant onboarding service façade.
# Sárközi Mihály - 2026.05.21

"""TenantSignupService – thin public facade over TenantSignupOrchestrator."""
from __future__ import annotations

from core.modules.tenant.signup.orchestrator import (
    DemoSignupResult,
    TenantSignupOrchestrator,
)


class TenantSignupService:
    def __init__(self, orchestrator: TenantSignupOrchestrator) -> None:
        self._orchestrator = orchestrator

    def is_slug_available(self, slug: str) -> bool:
        return self._orchestrator.is_slug_available(slug)

    def resolve_demo_login_redirect(self, token: str) -> str:
        return self._orchestrator.resolve_demo_login_redirect(token)

    def signup(self, **kwargs) -> DemoSignupResult:
        return self._orchestrator.signup(**kwargs)

    def request_demo_unsubscribe(self, **kwargs) -> dict[str, str | int]:
        return self._orchestrator.request_demo_unsubscribe(**kwargs)


__all__ = ["DemoSignupResult", "TenantSignupService"]
