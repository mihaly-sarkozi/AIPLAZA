"""TenantSignupService – thin public facade over TenantSignupOrchestrator."""
from __future__ import annotations

from core.extensions.tenant.signup.orchestrator import (
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
