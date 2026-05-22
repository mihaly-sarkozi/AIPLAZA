from __future__ import annotations

import pytest

from core.modules.tenant.signup import orchestrator as orchestrator_module
from core.modules.tenant.signup.errors import DemoSessionRequiredError
from core.modules.tenant.signup.orchestrator_result import DemoSignupResult

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_orchestrator_does_not_pass_extra_kwargs_to_resend_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_resend_kwargs: dict[str, object] = {}
    captured_new_signup_kwargs: dict[str, object] = {}

    class FakeSlugReserver:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class FakeResendUseCase:
        def __init__(self, **kwargs) -> None:
            captured_resend_kwargs.update(kwargs)

    class FakeNewSignupUseCase:
        def __init__(self, **kwargs) -> None:
            captured_new_signup_kwargs.update(kwargs)

    monkeypatch.setattr(orchestrator_module, "DemoSlugReserver", FakeSlugReserver)
    monkeypatch.setattr(orchestrator_module, "DemoSignupResendUseCase", FakeResendUseCase)
    monkeypatch.setattr(orchestrator_module, "DemoNewSignupUseCase", FakeNewSignupUseCase)

    hooks_provider = lambda: ()
    audit_service = object()

    orchestrator_module.TenantSignupOrchestrator(
        tenant_repository=object(),
        user_service=object(),
        provisioning_service=object(),
        demo_signup_repository=object(),
        demo_login_token_service=object(),
        tenant_base_domain="lvh.me",
        clock=object(),
        tenant_signup_hooks_provider=hooks_provider,
        audit_service=audit_service,
    )

    assert "tenant_signup_hooks_provider" not in captured_resend_kwargs
    assert "audit_service" not in captured_resend_kwargs
    assert "tenant_signup_hooks_provider" not in captured_new_signup_kwargs
    assert "audit_service" not in captured_new_signup_kwargs


def test_signup_requires_demo_session_id_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeSlugReserver:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def reserve(self, session_id: str, requested_name: str, email: str) -> str:
            captured["reserved_session_id"] = session_id
            captured["requested_name"] = requested_name
            captured["email"] = email
            return "demo"

    class FakeResendUseCase:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class FakeNewSignupUseCase:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def execute(self, **kwargs):
            captured["new_signup_session_id"] = kwargs["demo_session_id"]
            return DemoSignupResult(
                slug="demo",
                host_hint="demo.lvh.me",
                demo_login_token="token",
                created_new=True,
                resent_existing=False,
            )

    class FakeDemoSignupRepository:
        def is_email_blocked(self, email: str) -> bool:
            return False

        def find_latest_completed_tenant_slug_by_email(self, email: str):
            return None

    class FakeTenantRepository:
        def get_by_slug(self, slug: str):
            return None

    monkeypatch.setattr(orchestrator_module, "DemoSlugReserver", FakeSlugReserver)
    monkeypatch.setattr(orchestrator_module, "DemoSignupResendUseCase", FakeResendUseCase)
    monkeypatch.setattr(orchestrator_module, "DemoNewSignupUseCase", FakeNewSignupUseCase)

    orchestrator = orchestrator_module.TenantSignupOrchestrator(
        tenant_repository=FakeTenantRepository(),
        user_service=object(),
        provisioning_service=object(),
        demo_signup_repository=FakeDemoSignupRepository(),
        demo_login_token_service=object(),
        tenant_base_domain="lvh.me",
        clock=object(),
    )

    with pytest.raises(DemoSessionRequiredError):
        orchestrator.signup(
            email="demo@example.com",
            kb_name="Demo KB",
            name="Demo User",
            locale="hu",
            resend_existing_access=False,
            demo_session_id=None,
        )
