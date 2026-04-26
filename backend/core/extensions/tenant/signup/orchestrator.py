"""Tenant signup orchestrator.

Responsibility: validate incoming signup parameters and dispatch to the
appropriate focused use case:
- ``DemoSlugReserver``        – slug generation and reservation
- ``DemoSignupResendUseCase`` – resend existing demo access
- ``DemoNewSignupUseCase``    – brand-new demo tenant creation
- ``DemoUnsubscribeUseCase``  – deletion request and email block

This class is intentionally thin: all business logic lives in the use cases.
"""
from __future__ import annotations

from typing import Optional
from uuid import uuid4

from core.extensions.tenant.ports import TenantRepositoryPort
from core.extensions.tenant.slug.policy import normalize_demo_locale
from core.extensions.tenant.repositories.demo_signup_repository import DemoSignupRepository
from core.extensions.tenant.signup.new_demo_signup import DemoNewSignupUseCase
from core.extensions.tenant.signup.orchestrator_result import DemoSignupResult
from core.extensions.tenant.signup.resend_demo import DemoSignupResendUseCase
from core.extensions.tenant.slug.reservation import DemoSlugReserver
from core.extensions.tenant.tokens.demo_jwt import DemoLoginTokenService
from core.extensions.tenant.signup.unsubscribe import DemoUnsubscribeUseCase
from core.extensions.tenant.signup.errors import (
    DemoAlreadyExistsError,
    DemoEmailBlockedError,
    InvalidSlugError,
    NameRequiredError,
)
from core.platform.extensions.tenant_hooks import get_tenant_signup_hooks
from shared.utils.slug import slug_is_valid


class TenantSignupOrchestrator:
    def __init__(
        self,
        *,
        tenant_repository: TenantRepositoryPort,
        user_service,
        provisioning_service,
        demo_signup_repository: DemoSignupRepository,
        demo_login_token_service: DemoLoginTokenService,
        tenant_base_domain: str,
        clock,
        tenant_signup_hooks_provider=None,
        audit_service=None,
    ) -> None:
        self._tenant_repo = tenant_repository
        self._demo_signup_repo = demo_signup_repository
        self._clock = clock

        self._slug_reserver = DemoSlugReserver(
            tenant_repo=tenant_repository,
            demo_signup_repository=demo_signup_repository,
        )
        self._resend_use_case = DemoSignupResendUseCase(
            tenant_repo=tenant_repository,
            user_service=user_service,
            demo_signup_repository=demo_signup_repository,
            demo_login_token_service=demo_login_token_service,
            tenant_base_domain=tenant_base_domain,
            clock=clock,
        )
        self._new_signup_use_case = DemoNewSignupUseCase(
            tenant_repo=tenant_repository,
            user_service=user_service,
            provisioning_service=provisioning_service,
            demo_signup_repository=demo_signup_repository,
            demo_login_token_service=demo_login_token_service,
            tenant_base_domain=tenant_base_domain,
            clock=clock,
        )
        self._unsubscribe_use_case = DemoUnsubscribeUseCase(
            tenant_repo=tenant_repository,
            demo_signup_repository=demo_signup_repository,
            clock=clock,
        )
        self._demo_login_tokens = demo_login_token_service

    def is_slug_available(self, slug: str) -> bool:
        if not slug_is_valid(slug):
            return False
        return self._tenant_repo.get_by_slug(slug) is None

    def resolve_demo_login_redirect(self, token: str) -> str:
        return self._demo_login_tokens.resolve_demo_login_redirect(token)

    def _find_demo_tenant_by_email(self, email: str):
        slug = self._demo_signup_repo.find_latest_completed_tenant_slug_by_email(email)
        if not slug:
            return None
        return self._tenant_repo.get_by_slug(slug)

    @staticmethod
    def _ensure_demo_session_id(demo_session_id: str | None) -> str:
        normalized = (demo_session_id or "").strip()
        if normalized:
            return normalized
        return f"demo-{uuid4()}"

    def signup(
        self,
        *,
        email: str,
        kb_name: str | None,
        name: str,
        locale: str | None = None,
        resend_existing_access: bool = False,
        company_name: Optional[str] = None,
        address: Optional[str] = None,
        phone: Optional[str] = None,
        plan_code: str | None = "free",
        subscription_period: str | None = "monthly",
        demo_session_id: str | None = None,
    ) -> DemoSignupResult:
        del address, phone  # reserved for future use

        normalized_email = (email or "").strip().lower()
        owner_name = (name or "").strip()
        if self._demo_signup_repo.is_email_blocked(normalized_email):
            raise DemoEmailBlockedError()
        if not owner_name:
            raise NameRequiredError()
        demo_session_id = self._ensure_demo_session_id(demo_session_id)

        preferred_locale = normalize_demo_locale(locale)
        existing_tenant = self._find_demo_tenant_by_email(normalized_email)

        if existing_tenant is not None:
            if not resend_existing_access:
                raise DemoAlreadyExistsError()
            return self._resend_use_case.execute(
                existing_tenant=existing_tenant,
                email=normalized_email,
                preferred_locale=preferred_locale,
                owner_name=owner_name,
                demo_session_id=demo_session_id,
            )

        slug = self._slug_reserver.reserve(demo_session_id, owner_name, normalized_email)
        if not slug_is_valid(slug):
            raise InvalidSlugError()

        normalized_plan = (plan_code or "free").strip().lower() or "free"
        normalized_period = (subscription_period or "monthly").strip().lower() or "monthly"
        tenant_name = (company_name or owner_name or kb_name or slug).strip() or slug

        return self._new_signup_use_case.execute(
            slug=slug,
            email=normalized_email,
            owner_name=owner_name,
            tenant_name=tenant_name,
            preferred_locale=preferred_locale,
            plan_code=normalized_plan,
            subscription_period=normalized_period,
            demo_session_id=demo_session_id,
        )

    def request_demo_unsubscribe(
        self,
        *,
        tenant_slug: str,
        email: str,
        requested_by_user_id: int | None = None,
        current_user_email: str | None = None,
    ) -> dict[str, str | int]:
        return self._unsubscribe_use_case.execute(
            tenant_slug=tenant_slug,
            email=email,
            requested_by_user_id=requested_by_user_id,
            current_user_email=current_user_email,
        )


__all__ = ["DemoSignupResult", "TenantSignupOrchestrator"]
